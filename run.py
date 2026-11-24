"""
Main entrypoint for spot2ytm.
Starts the local server and automatically launches the web UI in your default browser.
"""

import sys
import time
import socket
import threading
import webbrowser
import uvicorn

DEFAULT_PORT = 5000


def find_free_port(start_port: int = DEFAULT_PORT) -> int:
    port = start_port
    while port < start_port + 50:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    return start_port


def open_browser(url: str, delay_seconds: float = 1.2):
    time.sleep(delay_seconds)
    print(f"\n🌐 Opening web dashboard in your browser: {url}\n")
    webbrowser.open(url)


def main():
    port = find_free_port()
    url = f"http://localhost:{port}"

    print("=" * 60)
    print(" 🎵 spot2ytm - Spotify to YouTube Music Migrator")
    print(f" Starting local server on: {url}")
    print("=" * 60)

    # Launch browser in a background thread once server starts
    threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    # Start FastAPI / Uvicorn server
    try:
        uvicorn.run("spot2ytm.app:app", host="127.0.0.1", port=port, log_level="info")
    except KeyboardInterrupt:
        print("\n\n👋 spot2ytm server stopped. Goodbye!\n")


if __name__ == "__main__":
    main()
