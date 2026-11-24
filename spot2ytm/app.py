"""
FastAPI Backend for spot2ytm.
Serves the web dashboard, manages Spotify extraction, YouTube matching,
and handles real-time streaming progress logs.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

from spot2ytm.spotify import SpotifyExtractor
from spot2ytm.matcher import MusicMatcher
from spot2ytm.cache import MatchCache

logger = logging.getLogger("spot2ytm")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="spot2ytm")

# Enable CORS for bookmarklet requests from open.spotify.com
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PrivateNetworkAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.headers.get("access-control-request-private-network"):
            response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response


app.add_middleware(PrivateNetworkAccessMiddleware)

extractor = SpotifyExtractor()
cache = MatchCache()
matcher = MusicMatcher(cache=cache)

WEB_DIR = Path(__file__).parent / "web"

# In-memory storage for Spotify library import
imported_spotify_playlists: List[Dict[str, Any]] = []
global_spotify_token: Optional[str] = None


class FetchRequest(BaseModel):
    url: str
    token: Optional[str] = None


class BulkFetchRequest(BaseModel):
    urls: List[str]
    token: Optional[str] = None


class SpotifyImportRequest(BaseModel):
    playlists: List[Dict[str, Any]]
    token: Optional[str] = None


@app.post("/api/spotify-import")
async def receive_spotify_import(req: SpotifyImportRequest):
    global imported_spotify_playlists, global_spotify_token
    imported_spotify_playlists = req.playlists
    if req.token:
        global_spotify_token = req.token
        logger.info("Saved user Spotify session token (enables private playlist access)")
    logger.info("Received %d imported Spotify playlists from bookmarklet", len(imported_spotify_playlists))
    return {"status": "ok", "count": len(imported_spotify_playlists)}


@app.get("/api/spotify-import")
async def get_spotify_import():
    return {"playlists": imported_spotify_playlists, "has_token": bool(global_spotify_token)}


@app.delete("/api/spotify-import")
async def clear_spotify_import():
    global imported_spotify_playlists, global_spotify_token
    imported_spotify_playlists = []
    global_spotify_token = None
    return {"status": "cleared"}


@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_file = WEB_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Web UI not found")
    with open(index_file, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/status")
async def get_status():
    return {
        "status": "ready",
        "cache_count": len(cache.data),
    }


@app.post("/api/fetch/stream")
async def fetch_and_match_stream(req: FetchRequest):
    """Server-Sent Events endpoint streaming verbose real-time progress for single playlist."""
    async def event_generator():
        try:
            auth_token = req.token or global_spotify_token
            yield f"data: {json.dumps({'type': 'log', 'level': 'info', 'message': 'Connecting to Spotify to extract playlist metadata...'})}\n\n"
            playlist = await asyncio.to_thread(extractor.get_playlist, req.url, auth_token)
            total = len(playlist.tracks)
            yield f"data: {json.dumps({'type': 'log', 'level': 'info', 'message': f'Extracted: \"{playlist.name}\" by {playlist.author} ({total} tracks)'})}\n\n"
            yield f"data: {json.dumps({'type': 'playlist_info', 'playlist': playlist.to_dict()})}\n\n"

            matches = []
            for i, track in enumerate(playlist.tracks):
                pct = int(((i) / max(1, total)) * 100)
                yield f"data: {json.dumps({'type': 'progress', 'current': i + 1, 'total': total, 'percent': pct, 'track_name': track.name, 'artist': track.primary_artist})}\n\n"

                m = await asyncio.to_thread(matcher.match_track, track)
                matches.append(m.to_dict())

                if m.match_type == "isrc":
                    level = "success"
                    msg = f"[{i+1}/{total}] ✓ ISRC Match: {track.artist_str} - {track.name} ➔ {m.youtube_title} ({m.confidence:.0f}%)"
                elif m.confidence >= 80:
                    level = "success"
                    msg = f"[{i+1}/{total}] ⚡ High Match: {track.artist_str} - {track.name} ➔ {m.youtube_title} ({m.confidence:.0f}%)"
                elif m.youtube_video_id:
                    level = "warning"
                    msg = f"[{i+1}/{total}] ~ Fuzzy Match: {track.artist_str} - {track.name} ➔ {m.youtube_title} ({m.confidence:.0f}%)"
                else:
                    level = "error"
                    msg = f"[{i+1}/{total}] ✗ Unmatched: {track.artist_str} - {track.name}"

                yield f"data: {json.dumps({'type': 'log', 'level': level, 'message': msg})}\n\n"
                yield f"data: {json.dumps({'type': 'track_match', 'index': i, 'match': m.to_dict()})}\n\n"

            matched_count = sum(1 for m in matches if m.get("youtube_video_id"))
            yield f"data: {json.dumps({'type': 'progress', 'current': total, 'total': total, 'percent': 100, 'track_name': 'Done', 'artist': ''})}\n\n"
            yield f"data: {json.dumps({'type': 'log', 'level': 'success', 'message': f'🎉 Matching finished! {matched_count}/{total} songs matched ({matched_count/max(1,total)*100:.0f}%).' })}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'playlist': playlist.to_dict(), 'matches': matches})}\n\n"

        except Exception as e:
            logger.exception("Error during fetch stream")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/fetch-bulk/stream")
async def fetch_and_match_bulk_stream(req: BulkFetchRequest):
    """Server-Sent Events endpoint streaming verbose real-time progress for bulk playlists."""
    async def event_generator():
        try:
            urls = [u.strip() for u in req.urls if u.strip()]
            total_playlists = len(urls)
            yield f"data: {json.dumps({'type': 'log', 'level': 'info', 'message': f'Starting bulk processing of {total_playlists} playlists...'})}\n\n"

            all_results = []
            total_tracks_all = 0
            total_matched_all = 0

            auth_token = req.token or global_spotify_token
            for p_idx, url in enumerate(urls):
                yield f"data: {json.dumps({'type': 'log', 'level': 'info', 'message': f'📂 [{p_idx+1}/{total_playlists}] Fetching metadata for {url}'})}\n\n"
                try:
                    playlist = await asyncio.to_thread(extractor.get_playlist, url, auth_token)
                except Exception as pe:
                    yield f"data: {json.dumps({'type': 'log', 'level': 'error', 'message': f'Failed to extract playlist {url}: {pe}'})}\n\n"
                    continue

                total_tracks = len(playlist.tracks)
                total_tracks_all += total_tracks
                yield f"data: {json.dumps({'type': 'log', 'level': 'info', 'message': f'📋 [{p_idx+1}/{total_playlists}] \"{playlist.name}\" loaded ({total_tracks} tracks)'})}\n\n"

                matches = []
                for i, track in enumerate(playlist.tracks):
                    pct = int(((i) / max(1, total_tracks)) * 100)
                    yield f"data: {json.dumps({'type': 'progress', 'current': i + 1, 'total': total_tracks, 'percent': pct, 'playlist_index': p_idx + 1, 'total_playlists': total_playlists, 'playlist_name': playlist.name, 'track_name': track.name, 'artist': track.primary_artist})}\n\n"

                    m = await asyncio.to_thread(matcher.match_track, track)
                    matches.append(m.to_dict())

                    if m.match_type == "isrc":
                        level = "success"
                        msg = f"  [{i+1}/{total_tracks}] ✓ ISRC: {track.artist_str} - {track.name} ➔ {m.youtube_title}"
                    elif m.confidence >= 80:
                        level = "success"
                        msg = f"  [{i+1}/{total_tracks}] ⚡ High: {track.artist_str} - {track.name} ➔ {m.youtube_title} ({m.confidence:.0f}%)"
                    elif m.youtube_video_id:
                        level = "warning"
                        msg = f"  [{i+1}/{total_tracks}] ~ Fuzzy: {track.artist_str} - {track.name} ➔ {m.youtube_title} ({m.confidence:.0f}%)"
                    else:
                        level = "error"
                        msg = f"  [{i+1}/{total_tracks}] ✗ Unmatched: {track.artist_str} - {track.name}"

                    yield f"data: {json.dumps({'type': 'log', 'level': level, 'message': msg})}\n\n"

                p_matched = sum(1 for m in matches if m.get("youtube_video_id"))
                total_matched_all += p_matched
                yield f"data: {json.dumps({'type': 'log', 'level': 'success', 'message': f'✓ Completed \"{playlist.name}\": {p_matched}/{total_tracks} matched.'})}\n\n"

                p_item = {"playlist": playlist.to_dict(), "matches": matches}
                all_results.append(p_item)
                yield f"data: {json.dumps({'type': 'playlist_done', 'index': p_idx, 'item': p_item})}\n\n"

            yield f"data: {json.dumps({'type': 'log', 'level': 'success', 'message': f'🎉 Bulk processing complete! {total_matched_all}/{total_tracks_all} tracks matched across {len(all_results)} playlists.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'items': all_results})}\n\n"

        except Exception as e:
            logger.exception("Error in bulk stream")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Fallback non-streaming endpoints
@app.post("/api/fetch")
async def fetch_and_match(req: FetchRequest):
    try:
        playlist = await asyncio.to_thread(extractor.get_playlist, req.url)
        matches = []
        for track in playlist.tracks:
            m = await asyncio.to_thread(matcher.match_track, track)
            matches.append(m.to_dict())
        return {
            "playlist": playlist.to_dict(),
            "matches": matches,
        }
    except Exception as e:
        logger.exception("Failed to fetch playlist")
        return {"error": str(e)}


@app.post("/api/fetch-bulk")
async def fetch_and_match_bulk(req: BulkFetchRequest):
    try:
        results = []
        for url in req.urls:
            url = url.strip()
            if not url:
                continue
            try:
                playlist = await asyncio.to_thread(extractor.get_playlist, url)
                matches = []
                for track in playlist.tracks:
                    m = await asyncio.to_thread(matcher.match_track, track)
                    matches.append(m.to_dict())
                results.append({
                    "playlist": playlist.to_dict(),
                    "matches": matches,
                })
            except Exception as e:
                logger.warning("Error fetching playlist %s: %s", url, e)
        return {"items": results}
    except Exception as e:
        logger.exception("Failed bulk fetch")
        return {"error": str(e)}
