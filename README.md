# spot2ytm 🎵➔📺

> Migrate Spotify playlists over to YouTube & YouTube Music with zero API keys, smart ISRC matching, and no daily quota limits.

`spot2ytm` is a local desktop web application that extracts Spotify playlist metadata, matches the songs against YouTube Music using spotDL-style matching algorithms, and syncs them directly to your YouTube library using an authenticated browser session.

---

## ✨ Features

- **🚀 Auto-Launching Web Dashboard**: Just run `python run.py` — it boots a local server and automatically pops open the clean, dark-mode web UI in your default browser.
- **🔑 Zero Spotify API Setup**: Built with `SpotipyFree`. Paste any public Spotify playlist URL and it extracts all tracks immediately without needing a Spotify Developer account or client secrets.
- **🎯 Precision Matching Engine**:
  - **ISRC First**: Queries YouTube Music by International Standard Recording Code for 100% verified track matches.
  - **Fuzzy + Duration Scoring**: Uses RapidFuzz token matching, strict duration tolerance (±4s), and negative keyword filtering (filters out live, slowed, reverb, acoustic, or fan covers unless requested).
- **⚡ Quota-Free YouTube Sync**: Standard YouTube Data API v3 enforces a 10,000 unit/day quota (adding 1 song costs 50 units = max 200 songs/day). `spot2ytm` uses a persistent Playwright session (`./.profile`) to sync playlists directly without API limits.
- **💾 Local Match Cache**: Matched tracks are cached in `.cache/matches.json` so re-syncing or updating large playlists is instantaneous.

---

## 🛠️ Quick Start

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/shamsghani/spot2ytm.git
cd spot2ytm

pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Launch the Application

```bash
python run.py
```

Your browser will automatically open to `http://localhost:5000`.

---

## 📖 How to Use

1. **Connect YouTube (One-Time)**:
   - On the top right of the dashboard, if it says **"Not Logged In"**, click **"Log in to YouTube"**.
   - A browser window will open to Google's sign-in page. Log into your Google account.
   - Your session is saved locally in `.profile/` so you only ever have to do this once.
2. **Load Spotify Playlist**:
   - Paste any public Spotify playlist URL (e.g., `https://open.spotify.com/playlist/...`).
   - Click **"Load & Match"**.
3. **Review Matches**:
   - Inspect the tracks table with confidence scores, matched YouTube video titles, and duration comparisons.
4. **Sync to YouTube**:
   - Customize the target playlist name if desired.
   - Click **"Sync to YouTube"** and watch the real-time progress bar as tracks are added to your YouTube / YouTube Music library.

---

## 🏗️ Architecture

```
[ Spotify URL ] ──▶ [ Spotify Extractor (SpotipyFree) ]
                            │
                            ▼ (Title, Artist, ISRC, Duration)
                    [ YouTube Music Matcher ]
                     ├─ 1. ISRC exact query
                     ├─ 2. "Artist - Title" search
                     └─ 3. Fuzzy & duration penalty filter
                            │
                            ▼ (Matched YouTube Video IDs)
                    [ Playwright Browser Manager ]
                     ├─ Persistent Google profile (.profile/)
                     └─ YouTube internal editPlaylist batch call
                            │
                            ▼
                    [ Target YouTube Playlist Created & Populated ]
```

---

## 📜 License

MIT License. Created for personal playlist migration.
