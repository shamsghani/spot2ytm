"""
FastAPI Backend for spot2ytm.
Serves the web dashboard, manages Spotify extraction, YouTube matching,
and handles streaming progress for playlist sync.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from spot2ytm.spotify import SpotifyExtractor
from spot2ytm.matcher import MusicMatcher
from spot2ytm.browser import YouTubeBrowserManager
from spot2ytm.cache import MatchCache

logger = logging.getLogger("spot2ytm")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="spot2ytm")

extractor = SpotifyExtractor()
cache = MatchCache()
matcher = MusicMatcher(cache=cache)
browser_manager = YouTubeBrowserManager()

WEB_DIR = Path(__file__).parent / "web"

# In-memory sync state and progress event stream
sync_state = {
    "is_syncing": False,
    "percent": 0,
    "message": "Idle",
    "done": False,
    "playlist_url": "",
    "error": None,
}


class FetchRequest(BaseModel):
    url: str


class SyncRequest(BaseModel):
    playlist_name: str
    video_ids: List[str]


@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_file = WEB_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Web UI not found")
    with open(index_file, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/status")
async def get_status():
    logged_in = await browser_manager.check_login_status()
    return {
        "logged_in": logged_in,
        "cache_count": len(cache.data),
        "sync_state": sync_state,
    }


@app.post("/api/login")
async def trigger_login(background_tasks: BackgroundTasks):
    background_tasks.add_task(browser_manager.launch_login_flow, 180)
    return {"status": "login_flow_started"}


@app.post("/api/fetch")
async def fetch_and_match(req: FetchRequest):
    try:
        # Run blocking network requests in threadpool
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


async def _perform_sync(playlist_name: str, video_ids: List[str]):
    sync_state["is_syncing"] = True
    sync_state["percent"] = 5
    sync_state["message"] = f"Initializing sync for {len(video_ids)} tracks..."
    sync_state["done"] = False
    sync_state["error"] = None

    def on_progress(current: int, total: int, msg: str):
        pct = int((current / max(1, total)) * 95)
        sync_state["percent"] = pct
        sync_state["message"] = msg

    try:
        result = await browser_manager.sync_playlist(
            playlist_name=playlist_name,
            video_ids=video_ids,
            progress_callback=on_progress,
        )
        sync_state["percent"] = 100
        sync_state["message"] = f"Successfully added {result.get('added', 0)} tracks to playlist!"
        sync_state["playlist_url"] = result.get("playlist_url", "")
        sync_state["done"] = True
    except Exception as e:
        logger.exception("Sync failed")
        sync_state["error"] = str(e)
        sync_state["message"] = f"Error: {e}"
        sync_state["done"] = True
    finally:
        sync_state["is_syncing"] = False


@app.post("/api/sync")
async def start_sync(req: SyncRequest, background_tasks: BackgroundTasks):
    if sync_state["is_syncing"]:
        return {"status": "already_syncing"}
    background_tasks.add_task(_perform_sync, req.playlist_name, req.video_ids)
    return {"status": "started"}


@app.get("/api/sync/stream")
async def sync_stream(request: Request):
    """Server-Sent Events endpoint streaming progress to the web UI."""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break

            data = json.dumps({
                "percent": sync_state["percent"],
                "message": sync_state["message"],
                "done": sync_state["done"],
                "playlist_url": sync_state["playlist_url"],
                "error": sync_state["error"],
            })
            yield f"data: {data}\n\n"

            if sync_state["done"]:
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
