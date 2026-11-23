"""
Spotify playlist metadata and track extractor.
Uses anonymous web tokens (SpotipyFree) so no Spotify API keys are required.
"""

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
from SpotipyFree import Spotify as FreeSpotify


@dataclass
class Track:
    id: str
    name: str
    artists: List[str]
    album: str
    duration_seconds: int
    isrc: Optional[str] = None
    cover_url: Optional[str] = None
    spotify_url: Optional[str] = None
    track_number: Optional[int] = None

    @property
    def primary_artist(self) -> str:
        return self.artists[0] if self.artists else "Unknown"

    @property
    def artist_str(self) -> str:
        return ", ".join(self.artists)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["primary_artist"] = self.primary_artist
        d["artist_str"] = self.artist_str
        return d


@dataclass
class PlaylistInfo:
    id: str
    name: str
    description: str
    author: str
    cover_url: Optional[str]
    total_tracks: int
    tracks: List[Track]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "cover_url": self.cover_url,
            "total_tracks": self.total_tracks,
            "tracks": [t.to_dict() for t in self.tracks],
        }


def extract_playlist_id(url_or_id: str) -> str:
    """Extract playlist ID from URL or return raw ID."""
    clean = url_or_id.strip()
    match = re.search(r"playlist[/:]([a-zA-Z0-9]+)", clean)
    if match:
        return match.group(1)
    if re.match(r"^[a-zA-Z0-9]{22}$", clean):
        return clean
    raise ValueError(f"Invalid Spotify playlist URL or ID: {url_or_id}")


class SpotifyExtractor:
    def __init__(self):
        self.client = FreeSpotify()

    def get_playlist(self, url_or_id: str) -> PlaylistInfo:
        playlist_id = extract_playlist_id(url_or_id)
        raw_playlist = self.client.playlist(playlist_id)
        if not raw_playlist:
            raise ValueError(f"Could not retrieve playlist metadata for ID {playlist_id}")

        name = raw_playlist.get("name") or "Untitled Playlist"
        description = raw_playlist.get("description") or ""
        owner = raw_playlist.get("owner", {}).get("display_name") or "Spotify User"

        images = raw_playlist.get("images") or []
        cover_url = images[0].get("url") if images else None

        # Paging tracks
        tracks: List[Track] = []
        playlist_items = self.client.playlist_items(playlist_id)

        items_list = []
        if playlist_items and "items" in playlist_items:
            items_list.extend(playlist_items["items"])
            while playlist_items.get("next"):
                playlist_items = self.client.next(playlist_items)
                if not playlist_items or "items" not in playlist_items:
                    break
                items_list.extend(playlist_items["items"])

        for idx, item in enumerate(items_list):
            if not isinstance(item, dict):
                continue
            track_data = item.get("track") or item.get("item")
            if not track_data or track_data.get("is_local") or track_data.get("type") != "track":
                continue

            track_id = track_data.get("id") or f"track_{idx}"
            duration_ms = track_data.get("duration_ms", 0)
            duration_sec = int(duration_ms / 1000)
            if duration_sec == 0:
                continue

            artists = [a.get("name") for a in track_data.get("artists", []) if a.get("name")]
            album_meta = track_data.get("album", {})
            album_name = album_meta.get("name") or ""
            album_images = album_meta.get("images") or []
            track_cover = album_images[0].get("url") if album_images else cover_url

            external_ids = track_data.get("external_ids", {})
            isrc = external_ids.get("isrc")
            spotify_url = track_data.get("external_urls", {}).get("spotify")

            tracks.append(
                Track(
                    id=track_id,
                    name=track_data.get("name", "Unknown Title"),
                    artists=artists if artists else ["Unknown Artist"],
                    album=album_name,
                    duration_seconds=duration_sec,
                    isrc=isrc,
                    cover_url=track_cover,
                    spotify_url=spotify_url,
                    track_number=track_data.get("track_number", idx + 1),
                )
            )

        return PlaylistInfo(
            id=playlist_id,
            name=name,
            description=description,
            author=owner,
            cover_url=cover_url,
            total_tracks=len(tracks),
            tracks=tracks,
        )
