"""
YouTube Music Matching Engine.
Matches Spotify tracks against the YouTube Music catalog using ISRC codes,
metadata search, duration tolerance, and fuzzy string distance scoring.
"""

import math
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from rapidfuzz import fuzz
from ytmusicapi import YTMusic

from spot2ytm.spotify import Track
from spot2ytm.cache import MatchCache

FORBIDDEN_WORDS = [
    "live",
    "remix",
    "cover",
    "slowed",
    "reverb",
    "karaoke",
    "acoustic",
    "8d audio",
    "tribute",
    "instrumental",
    "parody",
]

ISRC_REGEX = re.compile(r"^[A-Z]{2}-?\w{3}-?\d{2}-?\d{5}$")


def parse_duration_seconds(duration_str: Optional[str]) -> int:
    """Parse 'MM:SS' or 'H:MM:SS' into seconds."""
    if not duration_str:
        return 0
    parts = str(duration_str).split(":")
    try:
        if len(parts) == 1:
            return int(parts[0])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except (ValueError, TypeError):
        return 0
    return 0


def clean_title(title: str) -> str:
    """Strip common noise like (Official Video), [Audio], etc."""
    t = re.sub(r"\((official\s*(music\s*)?video|audio|lyric(s)?\s*video|visualizer)\)", "", title, flags=re.IGNORECASE)
    t = re.sub(r"\[(official\s*(music\s*)?video|audio|lyric(s)?\s*video|visualizer)\]", "", t, flags=re.IGNORECASE)
    return t.strip()


@dataclass
class MatchResult:
    spotify_track_id: str
    spotify_name: str
    spotify_artist: str
    youtube_video_id: Optional[str]
    youtube_title: Optional[str]
    youtube_artist: Optional[str]
    youtube_duration: Optional[int]
    confidence: float
    match_type: str  # 'isrc', 'high', 'medium', 'low', 'unmatched'
    youtube_url: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MusicMatcher:
    def __init__(self, cache: Optional[MatchCache] = None):
        self.ytm = YTMusic()
        self.cache = cache or MatchCache()

    def match_track(self, track: Track) -> MatchResult:
        # Check cache first
        cached = self.cache.get(track.id)
        if cached:
            return MatchResult(
                spotify_track_id=track.id,
                spotify_name=track.name,
                spotify_artist=track.primary_artist,
                youtube_video_id=cached.get("youtube_video_id"),
                youtube_title=cached.get("youtube_title"),
                youtube_artist=cached.get("youtube_artist"),
                youtube_duration=cached.get("youtube_duration"),
                confidence=cached.get("confidence", 95.0),
                match_type=cached.get("match_type", "cached"),
                youtube_url=cached.get("youtube_url"),
            )

        # 1. Try ISRC search if available
        if track.isrc:
            isrc_match = self._search_by_isrc(track)
            if isrc_match:
                self.cache.set(track.id, isrc_match.to_dict())
                return isrc_match

        # 2. Text Search with smart scoring
        text_match = self._search_by_text(track)
        if text_match and text_match.youtube_video_id:
            self.cache.set(track.id, text_match.to_dict())
            return text_match

        # 3. Unmatched
        res = MatchResult(
            spotify_track_id=track.id,
            spotify_name=track.name,
            spotify_artist=track.primary_artist,
            youtube_video_id=None,
            youtube_title=None,
            youtube_artist=None,
            youtube_duration=None,
            confidence=0.0,
            match_type="unmatched",
            youtube_url=None,
        )
        return res

    def _search_by_isrc(self, track: Track) -> Optional[MatchResult]:
        try:
            results = self.ytm.search(track.isrc, filter="songs", limit=5)
            if not results:
                return None

            for r in results:
                vid = r.get("videoId")
                if not vid:
                    continue

                duration_sec = parse_duration_seconds(r.get("duration"))
                dur_diff = abs(track.duration_seconds - duration_sec)

                # If duration is within 6 seconds, high confidence ISRC match!
                if dur_diff <= 6:
                    artists = [a.get("name") for a in r.get("artists", []) if a.get("name")]
                    artist_name = artists[0] if artists else "Unknown"
                    return MatchResult(
                        spotify_track_id=track.id,
                        spotify_name=track.name,
                        spotify_artist=track.primary_artist,
                        youtube_video_id=vid,
                        youtube_title=r.get("title", ""),
                        youtube_artist=artist_name,
                        youtube_duration=duration_sec,
                        confidence=99.0,
                        match_type="isrc",
                        youtube_url=f"https://www.youtube.com/watch?v={vid}",
                    )
        except Exception:
            pass
        return None

    def _search_by_text(self, track: Track) -> Optional[MatchResult]:
        query = f"{track.primary_artist} - {track.name}"
        candidates = []

        try:
            # First attempt: songs filter
            songs = self.ytm.search(query, filter="songs", limit=15)
            if songs:
                candidates.extend(songs)

            # Second attempt: videos filter if few results
            if len(candidates) < 3:
                videos = self.ytm.search(query, filter="videos", limit=10)
                if videos:
                    candidates.extend(videos)
        except Exception:
            return None

        if not candidates:
            return None

        best_candidate = None
        best_score = -1.0

        for cand in candidates:
            vid = cand.get("videoId")
            if not vid:
                continue

            score = self._score_candidate(track, cand)
            if score > best_score:
                best_score = score
                best_candidate = cand

        if best_candidate and best_score >= 50.0:
            vid = best_candidate["videoId"]
            artists = [a.get("name") for a in best_candidate.get("artists", []) if a.get("name")]
            artist_name = artists[0] if artists else "Unknown"
            duration_sec = parse_duration_seconds(best_candidate.get("duration"))

            match_type = "high" if best_score >= 80 else ("medium" if best_score >= 65 else "low")

            return MatchResult(
                spotify_track_id=track.id,
                spotify_name=track.name,
                spotify_artist=track.primary_artist,
                youtube_video_id=vid,
                youtube_title=best_candidate.get("title", ""),
                youtube_artist=artist_name,
                youtube_duration=duration_sec,
                confidence=round(best_score, 1),
                match_type=match_type,
                youtube_url=f"https://www.youtube.com/watch?v={vid}",
            )

        return None

    def _score_candidate(self, track: Track, cand: Dict[str, Any]) -> float:
        cand_title = clean_title(cand.get("title", ""))
        clean_track_name = clean_title(track.name)

        # 1. Title Similarity (0 - 45 pts)
        title_sim = fuzz.token_sort_ratio(clean_track_name.lower(), cand_title.lower())
        title_score = (title_sim / 100.0) * 45.0

        # 2. Artist Similarity (0 - 25 pts)
        cand_artists = [a.get("name", "").lower() for a in cand.get("artists", [])]
        cand_artist_str = " ".join(cand_artists)
        artist_sim = fuzz.partial_ratio(track.primary_artist.lower(), cand_artist_str)
        # Also check if artist is in title
        if artist_sim < 60:
            artist_in_title = fuzz.partial_ratio(track.primary_artist.lower(), cand_title.lower())
            artist_sim = max(artist_sim, artist_in_title)
        artist_score = (artist_sim / 100.0) * 25.0

        # 3. Duration Score (0 - 30 pts)
        cand_dur = parse_duration_seconds(cand.get("duration"))
        dur_diff = abs(track.duration_seconds - cand_dur) if cand_dur > 0 else 15

        if dur_diff <= 3:
            dur_score = 30.0
        elif dur_diff <= 8:
            dur_score = 25.0
        elif dur_diff <= 15:
            dur_score = 15.0
        elif dur_diff <= 30:
            dur_score = 5.0
        else:
            dur_score = -20.0  # Big penalty for huge length discrepancies

        total = title_score + artist_score + dur_score

        # 4. Forbidden Words Penalty
        title_lower = cand_title.lower()
        track_lower = clean_track_name.lower()
        for fw in FORBIDDEN_WORDS:
            if fw in title_lower and fw not in track_lower:
                total -= 30.0

        # Bonus for official song resultType
        if cand.get("resultType") == "song":
            total += 5.0

        return max(0.0, min(100.0, total))
