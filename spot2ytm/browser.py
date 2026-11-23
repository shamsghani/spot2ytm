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
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class YouTubeBrowserManager:
    def __init__(self, profile_dir: Path = PROFILE_DIR):
        self.profile_dir = profile_dir
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._lock = asyncio.Lock()
        self.is_logged_in: bool = False
        self.is_logging_in: bool = False

    async def get_context(self, headless: bool = True) -> BrowserContext:
        if self._context is not None:
            return self._context

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir.resolve()),
            headless=headless,
            user_agent=DEFAULT_UA,
            ignore_default_args=["--enable-automation"],
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
        if self.is_logging_in:
            if self._context:
                try:
                    cookies = await self._context.cookies(["https://www.youtube.com"])
                    cookie_names = {c["name"] for c in cookies}
                    if "SAPISID" in cookie_names or "LOGIN_INFO" in cookie_names:
                        self.is_logged_in = True
                except Exception:
                    pass
            return self.is_logged_in

        if self.is_logged_in:
            return True

        async with self._lock:
            try:
                ctx = await self.get_context(headless=True)
                cookies = await ctx.cookies(["https://www.youtube.com"])
                cookie_names = {c["name"] for c in cookies}
                self.is_logged_in = bool(cookie_names.intersection({"SAPISID", "SSID", "LOGIN_INFO"}))
                return self.is_logged_in
            except Exception as e:
                logger.error("Error checking login status: %s", e)
                return False

    async def launch_login_flow(self, timeout_seconds: int = 180) -> bool:
        """
        Launches headful browser to Google / YouTube login page and waits for user to sign in.
        """
        self.is_logging_in = True
        try:
            # Safely close existing headless context if running
            await self.close()

            # Launch visible headful browser
            ctx = await self.get_context(headless=False)
            page = await ctx.new_page()

            logger.info("Opening login window to YouTube sign-in...")
            await page.goto(
                "https://accounts.google.com/ServiceLogin?service=youtube&continue=https://www.youtube.com",
                wait_until="commit",
            )

            start_time = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
                await asyncio.sleep(2)
                try:
                    cookies = await ctx.cookies(["https://www.youtube.com"])
                    cookie_names = {c["name"] for c in cookies}
                    if "SAPISID" in cookie_names or "LOGIN_INFO" in cookie_names:
                        logger.info("Successfully detected YouTube login session!")
                        self.is_logged_in = True
                        await asyncio.sleep(1)
                        await page.close()
                        await self.close()
                        return True
                except Exception:
                    # Context might have been closed by user manually
                    break

            return self.is_logged_in
        finally:
            self.is_logging_in = False
            await self.close()

    async def sync_playlist(
        self,
        playlist_name: str,
        video_ids: List[str],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Creates (or opens) the target playlist on YouTube and adds video IDs.
        """
        async with self._lock:
            await self.close()  # Ensure clean context
            ctx = await self.get_context(headless=True)
            page = await ctx.new_page()

            try:
                # 1. Open YouTube to load ytcfg and user session context
                await page.goto("https://www.youtube.com", wait_until="networkidle")

                # 2. Get or create playlist
                playlist_id = await self._get_or_create_playlist(page, playlist_name)
                if not playlist_id:
                    raise RuntimeError("Failed to obtain or create YouTube playlist.")

                # 3. Add tracks in batches
                total = len(video_ids)
                added_count = 0
                batch_size = 20

                for i in range(0, total, batch_size):
                    batch = video_ids[i : i + batch_size]
                    success = await self._add_videos_batch(page, playlist_id, batch)

                    if success:
                        added_count += len(batch)
                    else:
                        for vid in batch:
                            single_ok = await self._add_videos_batch(page, playlist_id, [vid])
                            if single_ok:
                                added_count += 1
                            await asyncio.sleep(0.5)

                    if progress_callback:
                        progress_callback(
                            min(i + len(batch), total),
                            total,
                            f"Synced {min(i + len(batch), total)}/{total} tracks",
                        )
                    await asyncio.sleep(0.5)

                return {
                    "success": True,
                    "playlist_id": playlist_id,
                    "playlist_url": f"https://www.youtube.com/playlist?list={playlist_id}",
                    "total": total,
                    "added": added_count,
                }
            finally:
                await page.close()
                await self.close()

    async def _get_or_create_playlist(self, page: Page, name: str) -> Optional[str]:
        """Call YouTube internal API from page context to create or find a playlist."""
        script = """
        async (playlistTitle) => {
            try {
                const apiKey = window.ytcfg ? window.ytcfg.get('INNERTUBE_API_KEY') : null;
                const context = window.ytcfg ? window.ytcfg.get('INNERTUBE_CONTEXT') : null;
                if (!apiKey || !context) return { error: 'Missing ytcfg context' };

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
