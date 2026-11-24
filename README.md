# spot2ytm 🎵➔📺

> Seamlessly migrate Spotify playlists over to YouTube & YouTube Music with zero API keys, smart ISRC matching, live verbose activity logging, and no daily quota limits.

`spot2ytm` is a lightweight, portable desktop web application that extracts Spotify playlist metadata, matches songs against YouTube Music using spotDL-style matching algorithms, and syncs them directly to your YouTube library using your active browser session.

---

## ✨ Features

- **⚡ Click-and-Run Portability**: Just double-click `run.bat` on Windows (or run `./run.sh` on Mac/Linux). It automatically sets up dependencies, boots the local server, and launches the web UI in your browser.
- **🔑 Zero API Keys Required**: Built with `SpotipyFree`. Paste any Spotify playlist link and it extracts track details immediately without Spotify Developer credentials.
- **🎯 Precision Matching Engine**:
  - **ISRC First**: Queries YouTube Music by International Standard Recording Code for 100% verified track matches.
  - **Fuzzy + Duration Scoring**: Uses RapidFuzz token matching, strict duration tolerance (±4s), and negative keyword filtering (filters out fan covers, slowed/reverb, karaoke, or acoustic versions).
- **📋 Live Verbose Progress Console**: Real-time Server-Sent Events stream showing exact progress per track, ISRC detection, candidate scoring, and matching status directly in an embedded terminal log.
- **📚 Single & Bulk Playlist Support**: Migrate an individual playlist, paste batch links, or auto-import your entire Spotify library at once.
- **🪄 1-Click Spotify Library Auto-Detection**:
  - Drag the **"Extract Spotify Playlists"** bookmarklet to your browser.
  - Click it while logged into `open.spotify.com`.
  - It automatically extracts all your saved and created playlists and loads an interactive checklist on spot2ytm so you can pick and choose what to migrate!
- **🚀 100% In-Browser 1-Click Sync**:
  - **Option A (Drag Bookmarklet)**: Drag the bookmarklet to your bookmarks bar. Open YouTube Music and click it. No Google logins or secondary browser profiles needed!
  - **Option B (Included Chrome Extension)**: Load the included `extension/` folder in `chrome://extensions` for a permanent toolbar sync button.
  - **Option C (F12 Console Snippet)**: Quick copy-paste snippet for developer console sync.
- **💾 Local Match Cache**: Matched tracks are cached in `.cache/matches.json` so re-syncing or updating large playlists is instantaneous.

---

## 🛠️ Quick Start

### Windows (1-Click Run)
Simply double-click:
```
run.bat
```
*(On first run, it will automatically create a lightweight `.venv` and install the minimal dependencies).*

### macOS / Linux
```bash
git clone https://github.com/shamsghani/spot2ytm.git
cd spot2ytm
chmod +x run.sh
./run.sh
```

### Manual Run
```bash
pip install -r requirements.txt
python run.py
```

Your browser will automatically open to `http://localhost:5000`.

---

## 📖 How to Use

### Option 1: Auto-Import All Playlists from Your Spotify Account
1. On the web dashboard, click the **"Bulk / All Playlists"** tab.
2. Click **"Auto-Detect My Playlists"**.
3. Drag the **"Extract Spotify Playlists"** bookmarklet to your bookmarks bar.
4. Open [open.spotify.com](https://open.spotify.com) (make sure you are logged in) and click the bookmarklet!
5. When you return to spot2ytm, your entire Spotify library will be displayed in an interactive checklist:
   - Check/uncheck playlists, use search filter, or click "Select All".
   - Click **"Migrate Selected Playlists"** to start real-time batch matching!

### Option 2: Manual Playlist URL(s)
1. Paste a single Spotify playlist link or multiple links (one per line).
2. Click **"Load & Match"**.
3. Watch the **Live Matching Progress** terminal stream every track lookup, ISRC match, and confidence score in real time.
4. Review matches and click **"1-Click Sync to YouTube"** to instantly add them to your YouTube Music library!

---

## 📦 Lightweight Architecture

```
[ Spotify URL ] ──▶ [ Spotify Extractor (SpotipyFree) ]
                            │
                            ▼ (Title, Artist, ISRC, Duration)
                    [ YouTube Music Matcher ]
                     ├─ 1. ISRC exact query
                     ├─ 2. "Artist - Title" search
                     ├─ 3. Fuzzy & duration penalty filter
                            │
                            ▼ (Real-time SSE event stream)
                    [ Web Dashboard & Terminal Log ]
                            │
                            ▼ (InnerTube Batch Sync)
                    [ Target YouTube Playlist Created & Populated ]
```

---

## 📜 License

MIT License. Created for personal Spotify to YouTube Music playlist migration.
