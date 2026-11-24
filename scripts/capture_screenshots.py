"""
Script to capture high-resolution screenshots of spot2ytm for documentation.
"""

import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("docs/screenshots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PORT = 5000


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # High DPI 2x scale for crystal crisp screenshots
        context = browser.new_context(
            viewport={"width": 1280, "height": 840},
            device_scale_factor=2,
            color_scheme="dark"
        )
        page = context.new_page()
        page.goto(f"http://localhost:{PORT}")
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        # 1. Main Dashboard View
        print("Capturing 1. Dashboard...")
        page.screenshot(path=str(OUTPUT_DIR / "1_dashboard.png"))

        # 2. Bulk & Spotify Auto-Import Banner
        print("Capturing 2. Bulk Tab...")
        page.click("#tabBulk")
        time.sleep(0.5)
        page.screenshot(path=str(OUTPUT_DIR / "2_bulk_view.png"))

        # 3. Spotify Bookmarklet Modal
        print("Capturing 3. Spotify Import Modal...")
        page.click("button:has-text('Auto-Detect My Playlists')")
        time.sleep(0.6)
        page.screenshot(path=str(OUTPUT_DIR / "3_spotify_modal.png"))

        # 4. Spotify Library Checklist
        print("Capturing 4. Spotify Library Checklist...")
        page.evaluate("""() => {
            closeSpotifyImportModal();
            renderSpotifyChecklist([
                { id: "pl1", name: "Late Night Drive 🌙", author: "Shams", total_tracks: 42, cover_url: "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=120&auto=format&fit=crop&q=80", url: "https://open.spotify.com/playlist/pl1" },
                { id: "pl2", name: "Gym & High Energy 🔥", author: "Shams", total_tracks: 68, cover_url: "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=120&auto=format&fit=crop&q=80", url: "https://open.spotify.com/playlist/pl2" },
                { id: "pl3", name: "Chill Lo-Fi Beats ☕", author: "Spotify", total_tracks: 85, cover_url: "https://images.unsplash.com/photo-1501386761578-eac5c94b800a?w=120&auto=format&fit=crop&q=80", url: "https://open.spotify.com/playlist/pl3" },
                { id: "pl4", name: "Classic Rock Anthems 🎸", author: "Shams", total_tracks: 54, cover_url: "https://images.unsplash.com/photo-1498038432885-c6f3f1b912ee?w=120&auto=format&fit=crop&q=80", url: "https://open.spotify.com/playlist/pl4" },
                { id: "pl5", name: "Deep Focus & Study 📚", author: "Spotify", total_tracks: 110, cover_url: "https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?w=120&auto=format&fit=crop&q=80", url: "https://open.spotify.com/playlist/pl5" },
                { id: "pl6", name: "Summer Roadtrip ☀️", author: "Shams", total_tracks: 37, cover_url: "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=120&auto=format&fit=crop&q=80", url: "https://open.spotify.com/playlist/pl6" }
            ]);
        }""")
        time.sleep(0.8)
        page.screenshot(path=str(OUTPUT_DIR / "4_spotify_checklist.png"))

        # 5. Live Verbose Progress Console & Table
        print("Capturing 5. Live Matching Console...")
        page.evaluate("""() => {
            cancelSpotifyChecklist();
            const proc = document.getElementById('processingSection');
            proc.classList.remove('hidden');
            document.getElementById('progressBar').style.width = '68%';
            document.getElementById('progressPill').textContent = '68%';
            document.getElementById('processingTitle').textContent = 'Matching: "Late Night Drive 🌙" (42 tracks)';
            document.getElementById('processingSubtitle').textContent = '[29/42] The Weeknd - Blinding Lights';
            
            clearActivityLog();
            appendLog('Connecting to Spotify to extract playlist metadata...', 'info');
            appendLog('Extracted: "Late Night Drive 🌙" by Shams (42 tracks)', 'info');
            appendLog('[1/42] ✓ ISRC Match: The Weeknd - Starboy ➔ Starboy (Official Video) (100%)', 'success');
            appendLog('[2/42] ✓ ISRC Match: Kavinsky - Nightcall ➔ Nightcall (Drive Soundtrack) (100%)', 'success');
            appendLog('[3/42] ⚡ High Match: Daft Punk - Instant Crush ➔ Instant Crush (feat. Julian Casablancas) (96%)', 'success');
            appendLog('[4/42] ✓ ISRC Match: Glass Animals - Heat Waves ➔ Heat Waves (Official Audio) (100%)', 'success');
            appendLog('[5/42] ~ Fuzzy Match: Childish Gambino - Redbone ➔ Redbone (Official Track) (88%)', 'warning');
            appendLog('[6/42] ✓ ISRC Match: Arctic Monkeys - 505 ➔ 505 (Official Audio) (100%)', 'success');
            appendLog('[7/42] ⚡ High Match: M83 - Midnight City ➔ Midnight City (Remastered) (94%)', 'success');

            currentPlaylist = {
                id: 'pl1',
                name: 'Late Night Drive 🌙',
                author: 'Shams',
                total_tracks: 42,
                cover_url: 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=120&auto=format&fit=crop&q=80'
            };
            currentMatches = [
                { spotify_name: 'Starboy', spotify_artist: 'The Weeknd, Daft Punk', youtube_video_id: 'dqt8Z1k0oTQ', youtube_title: 'The Weeknd - Starboy (Official Music Video) ft. Daft Punk', youtube_duration: 230, confidence: 100, match_type: 'isrc', youtube_url: 'https://www.youtube.com/watch?v=dqt8Z1k0oTQ' },
                { spotify_name: 'Nightcall', spotify_artist: 'Kavinsky', youtube_video_id: 'MV_3Dpw-BRY', youtube_title: 'Kavinsky - Nightcall (Drive Original Soundtrack)', youtube_duration: 259, confidence: 100, match_type: 'isrc', youtube_url: 'https://www.youtube.com/watch?v=MV_3Dpw-BRY' },
                { spotify_name: 'Instant Crush', spotify_artist: 'Daft Punk, Julian Casablancas', youtube_video_id: 'a5uQMwRMHcs', youtube_title: 'Daft Punk - Instant Crush (Official Video) ft. Julian Casablancas', youtube_duration: 339, confidence: 96, match_type: 'high', youtube_url: 'https://www.youtube.com/watch?v=a5uQMwRMHcs' },
                { spotify_name: 'Heat Waves', spotify_artist: 'Glass Animals', youtube_video_id: 'mRD0-GxqHVo', youtube_title: 'Glass Animals - Heat Waves (Official Video)', youtube_duration: 239, confidence: 100, match_type: 'isrc', youtube_url: 'https://www.youtube.com/watch?v=mRD0-GxqHVo' }
            ];
            renderPlaylist();
        }""")
        time.sleep(0.8)
        page.screenshot(path=str(OUTPUT_DIR / "5_matching_console.png"))

        # 6. YouTube 1-Click Sync Modal
        print("Capturing 6. YouTube Sync Modal...")
        page.evaluate("""() => { openInBrowserModal(); }""")
        time.sleep(0.6)
        page.screenshot(path=str(OUTPUT_DIR / "6_youtube_sync_modal.png"))

        browser.close()
        print("All screenshots successfully captured!")


if __name__ == "__main__":
    run()
