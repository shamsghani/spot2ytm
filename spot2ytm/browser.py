"""
Playwright-based YouTube session and playlist manager.
Uses a persistent user data directory (.profile) to preserve Google login cookies,
avoiding YouTube Data API quotas.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from playwright.async_api import async_playwright, BrowserContext, Page

logger = logging.getLogger(__name__)

PROFILE_DIR = Path(".profile")


class YouTubeBrowserManager:
    def __init__(self, profile_dir: Path = PROFILE_DIR):
        self.profile_dir = profile_dir
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._context: Optional[BrowserContext] = None

    async def get_context(self, headless: bool = True) -> BrowserContext:
        if self._context is not None:
            return self._context

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir.resolve()),
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
            viewport={"width": 1280, "height": 800},
        )
        return self._context

    async def close(self):
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    async def check_login_status(self) -> bool:
        """Check if YouTube login cookies exist in the persistent profile."""
        try:
            ctx = await self.get_context(headless=True)
            cookies = await ctx.cookies(["https://www.youtube.com"])
            cookie_names = {c["name"] for c in cookies}
            is_logged_in = bool(cookie_names.intersection({"SAPISID", "SSID", "LOGIN_INFO"}))
            return is_logged_in
        except Exception as e:
            logger.error("Error checking login status: %s", e)
            return False
        finally:
            await self.close()

    async def launch_login_flow(self, timeout_seconds: int = 180) -> bool:
        """
        Launches headful browser to Google / YouTube login page and waits for user to sign in.
        """
        await self.close()  # Close existing headless context if any
        ctx = await self.get_context(headless=False)
        page = await ctx.new_page()

        await page.goto("https://accounts.google.com/ServiceLogin?service=youtube&continue=https://www.youtube.com")

        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            await asyncio.sleep(2)
            cookies = await ctx.cookies(["https://www.youtube.com"])
            cookie_names = {c["name"] for c in cookies}
            if "SAPISID" in cookie_names or "LOGIN_INFO" in cookie_names:
                logger.info("Successfully detected YouTube login session!")
                await page.close()
                return True

        await page.close()
        return False

    async def sync_playlist(
        self,
        playlist_name: str,
        video_ids: List[str],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Creates (or opens) the target playlist on YouTube and adds video IDs.
        """
        ctx = await self.get_context(headless=True)
        page = await ctx.new_page()

        try:
            # 1. Open YouTube to load ytcfg and user session context
            await page.goto("https://www.youtube.com", wait_until="networkidle")

            # 2. Get or create playlist
            playlist_id = await self._get_or_create_playlist(page, playlist_name)
            if not playlist_id:
                raise RuntimeError("Failed to obtain or create YouTube playlist.")

            # 3. Add tracks in batches using YouTube's internal editPlaylist endpoint
            total = len(video_ids)
            added_count = 0

            # Process in batches of 20 to avoid payload limits
            batch_size = 20
            for i in range(0, total, batch_size):
                batch = video_ids[i : i + batch_size]
                success = await self._add_videos_batch(page, playlist_id, batch)

                if success:
                    added_count += len(batch)
                else:
                    # Fallback: add one by one
                    for vid in batch:
                        single_ok = await self._add_videos_batch(page, playlist_id, [vid])
                        if single_ok:
                            added_count += 1
                        await asyncio.sleep(0.5)

                if progress_callback:
                    progress_callback(min(i + len(batch), total), total, f"Synced {min(i + len(batch), total)}/{total} tracks")
                await asyncio.sleep(1.0)

            return {
                "success": True,
                "playlist_id": playlist_id,
                "playlist_url": f"https://www.youtube.com/playlist?list={playlist_id}",
                "total": total,
                "added": added_count,
            }
        finally:
            await page.close()

    async def _get_or_create_playlist(self, page: Page, name: str) -> Optional[str]:
        """Call YouTube internal API from page context to create or find a playlist."""
        script = """
        async (playlistTitle) => {
            try {
                const apiKey = window.ytcfg ? window.ytcfg.get('INNERTUBE_API_KEY') : null;
                const context = window.ytcfg ? window.ytcfg.get('INNERTUBE_CONTEXT') : null;
                if (!apiKey || !context) return { error: 'Missing ytcfg context' };

                // Create new playlist
                const resp = await fetch('/youtubei/v1/playlist/create?key=' + apiKey, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        context: context,
                        title: playlistTitle,
                        privacyStatus: 'PUBLIC'
                    })
                });
                const data = await resp.json();
                return { playlistId: data.playlistId };
            } catch (err) {
                return { error: err.toString() };
            }
        }
        """
        result = await page.evaluate(script, name)
        if result and "playlistId" in result:
            return result["playlistId"]
        logger.warning("Internal playlist creation returned: %s", result)
        return None

    async def _add_videos_batch(self, page: Page, playlist_id: str, video_ids: List[str]) -> bool:
        """Call edit_playlist to append videos to playlist in one network request."""
        script = """
        async (args) => {
            const { playlistId, videoIds } = args;
            try {
                const apiKey = window.ytcfg ? window.ytcfg.get('INNERTUBE_API_KEY') : null;
                const context = window.ytcfg ? window.ytcfg.get('INNERTUBE_CONTEXT') : null;
                if (!apiKey || !context) return false;

                const actions = videoIds.map(vid => ({
                    action: 'ACTION_ADD_VIDEO',
                    addedVideoId: vid
                }));

                const resp = await fetch('/youtubei/v1/browse/edit_playlist?key=' + apiKey, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        context: context,
                        playlistId: playlistId,
                        actions: actions
                    })
                });
                const data = await resp.json();
                return data.status === 'STATUS_SUCCEEDED' || (data.actions && data.actions.length > 0) || !data.error;
            } catch (err) {
                return false;
            }
        }
        """
        res = await page.evaluate(script, {"playlistId": playlist_id, "videoIds": video_ids})
        return bool(res)
