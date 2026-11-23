document.getElementById('syncBtn').addEventListener('click', async () => {
  const url = document.getElementById('spotifyUrl').value.trim();
  const customName = document.getElementById('playlistName').value.trim();
  const statusDiv = document.getElementById('status');
  const btn = document.getElementById('syncBtn');

  if (!url) {
    statusDiv.textContent = 'Please enter a Spotify playlist URL.';
    return;
  }

  btn.disabled = true;
  statusDiv.textContent = '1/3 Fetching Spotify tracks & matching on YouTube Music...';

  try {
    // 1. Fetch matched tracks via local spot2ytm server
    const fetchRes = await fetch('http://localhost:5000/api/fetch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const data = await fetchRes.json();
    if (data.error) throw new Error(data.error);

    const playlistName = customName || data.playlist.name;
    const videoIds = data.matches.map(m => m.youtube_video_id).filter(Boolean);

    if (videoIds.length === 0) {
      throw new Error('No matched videos found for this playlist.');
    }

    statusDiv.textContent = `2/3 Matched ${videoIds.length} tracks. Creating playlist in your active YouTube tab...`;

    // 2. Execute playlist creation inside active YouTube / YouTube Music tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.url.includes('youtube.com')) {
      // Open YouTube Music tab if not already on it
      const newTab = await chrome.tabs.create({ url: 'https://music.youtube.com' });
      statusDiv.textContent = 'Opened YouTube Music. Click Migrate again once the tab loads.';
      btn.disabled = false;
      return;
    }

    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: inTabCreatePlaylist,
      args: [playlistName, videoIds]
    }, (results) => {
      btn.disabled = false;
      if (chrome.runtime.lastError) {
        statusDiv.textContent = 'Error: ' + chrome.runtime.lastError.message;
        return;
      }
      const res = results[0]?.result;
      if (res && res.playlistId) {
        statusDiv.innerHTML = `🎉 Success! Created playlist: <a href="https://music.youtube.com/playlist?list=${res.playlistId}" target="_blank">View Playlist</a>`;
        chrome.tabs.update(tab.id, { url: `https://music.youtube.com/playlist?list=${res.playlistId}` });
      } else {
        statusDiv.textContent = 'Sync completed or response: ' + JSON.stringify(res);
      }
    });

  } catch (err) {
    btn.disabled = false;
    statusDiv.textContent = 'Error: ' + err.message;
  }
});

async function inTabCreatePlaylist(title, videoIds) {
  try {
    const apiKey = window.ytcfg ? window.ytcfg.get('INNERTUBE_API_KEY') : null;
    const context = window.ytcfg ? window.ytcfg.get('INNERTUBE_CONTEXT') : null;
    if (!apiKey || !context) return { error: 'Missing ytcfg. Are you on YouTube/YouTube Music?' };

    const match = document.cookie.match(/SAPISID=([^;]+)/);
    if (!match) return { error: 'Not logged into YouTube in this tab.' };

    const sapisid = match[1];
    const timestamp = Math.floor(Date.now() / 1000);
    const origin = window.location.origin;
    const encoder = new TextEncoder();
    const data = encoder.encode(`${timestamp} ${sapisid} ${origin}`);
    const hashBuffer = await crypto.subtle.digest('SHA-1', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const sapisidHash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `SAPISIDHASH ${timestamp}_${sapisidHash}`,
      'X-Origin': origin
    };

    const resp = await fetch(`/youtubei/v1/playlist/create?key=${apiKey}`, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        context: context,
        title: title,
        videoIds: videoIds
      })
    });

    const dataRes = await resp.json();
    return { playlistId: dataRes.playlistId };
  } catch (err) {
    return { error: err.toString() };
  }
}
