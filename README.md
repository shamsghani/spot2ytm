# spot2ytm 🎵➔📺

[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-teal.svg)](https://www.python.org/)
[![Platform: Windows | macOS | Linux](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-blue.svg)]()
[![Zero API Keys](https://img.shields.io/badge/API%20Keys-Zero%20Required-success.svg)]()

> Migrate your Spotify playlists (public AND private) to YouTube & YouTube Music with **zero API keys**, **smart ISRC matching**, and **no daily quota or track limits**.

`spot2ytm` is a lightweight, portable local web application that extracts your Spotify playlists, matches songs against YouTube Music using spotDL-style precision matching, and syncs them directly into your YouTube library with 1 click in your active browser session.

---

## ⚡ Why spot2ytm vs Other Services?

| Feature | Paid Services (TuneMyMusic / Soundiiz) | Official YouTube API Tools | spot2ytm 🎵 |
| :--- | :---: | :---: | :---: |
| **Price** | Free tier capped at 500 songs; $4.50+/mo | Free | **100% Free Forever** |
| **Daily Limits** | 500 songs per month on free tier | Capped by strict 10k daily API quota | **Unlimited Playlists & Tracks** |
| **API Keys / Setup** | Requires third-party account linkage | Complex Google Cloud & Spotify Developer setup | **Zero API Keys or Developer Accounts** |
| **Private Playlists** | Requires granting broad OAuth access | Requires manual scopes | **Automatic via 1-Click Session Bookmark** |
| **Privacy** | Your library is stored on third-party servers | Cloud hosted | **100% Local (Runs on your own machine)** |

---

## ✨ Features

- **⚡ Click-and-Run Portability**: Just double-click `run.bat` on Windows (or run `./run.sh` on Mac/Linux). It automatically sets up dependencies, boots the local server, and pops open the web UI in your browser.
- **🪄 1-Click Spotify Library Auto-Detection**:
  - Drag the **"Extract Spotify Playlists"** bookmarklet to your browser.
  - Click it while logged into `open.spotify.com`.
  - It automatically extracts all your saved and created playlists (including **private playlists**) and loads an interactive checklist so you can pick and choose what to migrate!
- **🎯 Precision Matching Engine**:
  - **ISRC First**: Queries YouTube Music by International Standard Recording Code for 100% verified track matches.
  - **Fuzzy + Duration Scoring**: Uses RapidFuzz token matching, strict duration tolerance (±4s), and negative keyword filtering (filters out fan covers, live recordings, slowed/reverb, karaoke, or acoustic versions).
- **📋 Live Verbose Progress Console**: Real-time Server-Sent Events stream showing exact progress per track, ISRC detection, candidate scoring, and matching status directly in an embedded terminal log.
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
*(On first run, it will automatically create a lightweight virtual environment and install the minimal dependencies in ~10 seconds).*

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

### Option 1: Auto-Import All Playlists from Your Spotify Account (Recommended)
1. In the web dashboard, click the **"Bulk / All Playlists"** tab.
2. Click **"Auto-Detect My Playlists"**.
3. Drag the **"Extract Spotify Playlists"** bookmarklet to your bookmarks bar *(Press `Ctrl+Shift+B` or `Cmd+Shift+B` if your bookmarks bar is hidden)*.
4. Open [open.spotify.com](https://open.spotify.com) (make sure you are logged in) and click the bookmarklet!
5. When you return to spot2ytm, your entire Spotify library will appear in an interactive checklist:
   - Check/uncheck playlists, use the instant search filter, or click "Select All".
   - Click **"Migrate Selected Playlists"** to start real-time batch matching!
6. Once matching finishes, click **"1-Click Sync to YouTube"** to add all playlists directly to your YouTube Music account!

### Option 2: Manual Playlist URL(s)
1. Paste a single Spotify playlist link or multiple links (one per line).
2. Click **"Load & Match"**.
3. Watch the **Live Matching Progress** terminal stream every track lookup, ISRC match, and confidence score in real time.
4. Review matches and click **"1-Click Sync to YouTube"** to instantly add them to your YouTube Music library!

---

## ❓ Frequently Asked Questions (FAQ)

<details>
<summary><strong>Does this work for private playlists?</strong></summary>
Yes! When using the 1-click Spotify bookmarklet, it captures your active web player session token, allowing the backend to load all private, unlisted, and collaborative playlists directly.
</details>

<details>
<summary><strong>Do I need Spotify or YouTube API keys?</strong></summary>
No! spot2ytm requires zero API keys, zero client secrets, and zero developer accounts. It extracts Spotify metadata via public web tokens and syncs to YouTube using your active browser session.
</details>

<details>
<summary><strong>Is my login data or Google account safe?</strong></summary>
100% safe. spot2ytm runs entirely on your local machine (`localhost`). You never enter your Google or Spotify passwords into the app, and no cookies or tokens are ever sent to any remote server.
</details>

<details>
<summary><strong>What happens to songs that don't have an exact match?</strong></summary>
The matching engine scores candidates using strict duration matching (±4 seconds) and fuzzy title/artist similarity while rejecting live, remix, and cover versions. If no confident match exists, the track is safely marked as "Skipped" in the preview table so you don't end up with incorrect songs in your library.
</details>

---

## 📦 Architecture

```
[ Spotify Account / URL ] ──▶ [ Spotify Extractor (SpotipyFree + Session Token) ]
                                      │
                                      ▼ (Title, Artist, ISRC, Duration)
                              [ YouTube Music Matcher ]
                               ├─ 1. ISRC exact query
                               ├─ 2. "Artist - Title" search
                               └─ 3. Fuzzy & duration penalty filter
                                      │
                                      ▼ (Real-time SSE event stream)
                              [ Web Dashboard & Terminal Log ]
                                      │
                                      ▼ (InnerTube Batch Sync)
                              [ Target YouTube Playlists Created & Populated ]
```

---

## 📜 License

MIT License. Created for personal Spotify to YouTube Music playlist migration.
