"""
Playwright-based YouTube session and playlist manager.
Uses a persistent user data directory (.profile) to preserve Google login cookies,
avoiding YouTube Data API quotas.
"""

import asyncio
import logging
import os
import shutil
import sqlite3
import tempfile
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
        self.is_logging_in: bool = False

    def clean_stale_locks(self):
        """Remove stale Chromium SingletonLock files if no context is open."""
        if self._context is not None:
            return
        lock_files = [
            self.profile_dir / "SingletonLock",
            self.profile_dir / "SingletonCookie",
            self.profile_dir / "SingletonSocket",
        ]
        for f in lock_files:
            try:
                if f.exists():
                    f.unlink(missing_ok=True)
            except Exception:
                pass

    async def get_context(self, headless: bool = True) -> BrowserContext:
        if self._context is not None:
            return self._context

        self.clean_stale_locks()

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
        self.clean_stale_locks()

    async def check_login_status(self) -> bool:
        """
        Fast, non-blocking login check.
        Inspects the local SQLite cookie store or active browser context
        without launching any background browser process.
        """
        # If headful browser is currently open for login, inspect it live
        if self._context is not None:
            try:
                cookies = await self._context.cookies(["https://www.youtube.com"])
                names = {c["name"] for c in cookies}
                return bool(names.intersection({"SAPISID", "SSID", "LOGIN_INFO"}))
            except Exception:
                pass

        # Otherwise read from SQLite cookie file directly (0ms, zero locks)
        return self._check_cookies_on_disk()

    def _check_cookies_on_disk(self) -> bool:
        cookie_db_paths = [
            self.profile_dir / "Default" / "Network" / "Cookies",
            self.profile_dir / "Default" / "Cookies",
        ]
        db_path = next((p for p in cookie_db_paths if p.exists()), None)
        if not db_path:
            return False

        temp_db = None
        try:
            # Copy to temp file so we don't hold any lock on Chromium's file
            fd, temp_db = tempfile.mkstemp(suffix=".sqlite")
            os.close(fd)
            shutil.copy2(db_path, temp_db)

            with sqlite3.connect(temp_db) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM cookies WHERE host_key LIKE ? AND name IN ('SAPISID', 'SSID', 'LOGIN_INFO')",
                    ("%youtube.com%",),
                )
                rows = cursor.fetchall()
                return len(rows) > 0
        except Exception as e:
            logger.debug("Error checking cookie db on disk: %s", e)
            return False
        finally:
            if temp_db and os.path.exists(temp_db):
                try:
                    os.unlink(temp_db)
                except Exception:
                    pass

    async def launch_login_flow(self, timeout_seconds: int = 180) -> bool:
        """
        Launches headful browser to Google / YouTube login page and waits for user to sign in.
        """
        async with self._lock:
            self.is_logging_in = True
            try:
                # Ensure clean slate
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
                            await asyncio.sleep(1)
                            await page.close()
                            await self.close()
                            return True
                    except Exception:
                        # Window might have been closed by user
                        break

                return False
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
            await self.close()
            ctx = await self.get_context(headless=True)
            page = await ctx.new_page()

            try:
                await page.goto("https://www.youtube.com", wait_until="networkidle")

                playlist_id = await self._get_or_create_playlist(page, playlist_name)
                if not playlist_id:
                    raise RuntimeError("Failed to obtain or create YouTube playlist.")

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
