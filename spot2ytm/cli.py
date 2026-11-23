"""
CLI interface for spot2ytm.
Supports commands:
  spot2ytm web                  (Launch web dashboard)
  spot2ytm sync <spotify_url>   (Direct CLI sync)
  spot2ytm match <spotify_url>  (Inspect matches only)
"""

import argparse
import asyncio
import sys
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from spot2ytm.spotify import SpotifyExtractor
from spot2ytm.matcher import MusicMatcher
from spot2ytm.browser import YouTubeBrowserManager
from spot2ytm.cache import MatchCache

console = Console()


def format_duration(seconds: int) -> str:
    m = seconds // 60
    s = seconds % 60
    return f"{m}:{s:02d}"


def cli_match(url: str):
    console.print(f"[bold cyan]🔍 Extracting Spotify Playlist:[/bold cyan] {url}")
    extractor = SpotifyExtractor()
    cache = MatchCache()
    matcher = MusicMatcher(cache=cache)

    try:
        with console.status("[bold green]Fetching playlist tracks..."):
            playlist = extractor.get_playlist(url)

        console.print(f"[bold green]✔[/bold green] Found [bold]{playlist.total_tracks}[/bold] tracks in [bold]'{playlist.name}'[/bold] by {playlist.author}\n")

        table = Table(title=f"Matches for {playlist.name}", show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Spotify Track", style="bold white")
        table.add_column("Matched YouTube Title", style="cyan")
        table.add_column("Dur", justify="center", width=7)
        table.add_column("Score", justify="center", width=12)

        matched_ids = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Matching tracks on YouTube Music...", total=len(playlist.tracks))
            for idx, track in enumerate(playlist.tracks, start=1):
                match = matcher.match_track(track)
                progress.advance(task)

                score_style = "green" if match.confidence >= 80 else ("yellow" if match.confidence >= 50 else "red")
                match_label = f"[{score_style}]{match.match_type.upper()} ({match.confidence}%)[/{score_style}]"

                if match.youtube_video_id:
                    matched_ids.append(match.youtube_video_id)
                    yt_title = f"{match.youtube_title} ({match.youtube_artist})"
                    dur = format_duration(match.youtube_duration or 0)
                else:
                    yt_title = "[red italic]No match found[/red italic]"
                    dur = "--:--"

                table.add_row(str(idx), f"{track.name}\n[dim]{track.primary_artist}[/dim]", yt_title, dur, match_label)

        console.print(table)
        console.print(f"\n[bold green]Matched {len(matched_ids)} / {playlist.total_tracks} tracks.[/bold green]")
        return playlist, matched_ids

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return None, []


def cli_sync(url: str, playlist_name: str = None):
    playlist, video_ids = cli_match(url)
    if not playlist or not video_ids:
        return

    target_name = playlist_name or playlist.name
    console.print(f"\n[bold yellow]🚀 Preparing to sync {len(video_ids)} tracks to YouTube playlist: '{target_name}'[/bold yellow]")

    browser = YouTubeBrowserManager()

    async def run_sync():
        is_logged_in = await browser.check_login_status()
        if not is_logged_in:
            console.print("[bold red]Not logged into YouTube.[/bold red] Opening browser window to sign in...")
            ok = await browser.launch_login_flow(180)
            if not ok:
                console.print("[bold red]Login timed out or was not detected.[/bold red]")
                return

        console.print("[bold green]✔ YouTube login active.[/bold green] Creating and populating playlist...")

        with Progress(console=console) as progress:
            task = progress.add_task("[green]Syncing tracks...", total=len(video_ids))

            def on_progress(cur, total, msg):
                progress.update(task, completed=cur, description=f"[green]{msg}")

            result = await browser.sync_playlist(target_name, video_ids, on_progress)
            console.print(f"\n[bold green]✔ Done! Created playlist:[/bold green] {result.get('playlist_url')}")

    asyncio.run(run_sync())


def cli_login():
    console.print("[bold cyan]Opening Google sign-in window...[/bold cyan]")
    browser = YouTubeBrowserManager()
    ok = asyncio.run(browser.launch_login_flow(180))
    if ok:
        console.print("[bold green]✔ YouTube login successfully saved to .profile![/bold green]")
    else:
        console.print("[bold red]Login timed out or window was closed.[/bold red]")


def main():
    parser = argparse.ArgumentParser(description="spot2ytm: Spotify to YouTube Music Migrator")
    subparsers = parser.add_subparsers(dest="command")

    # web command
    subparsers.add_parser("web", help="Launch the local web dashboard")

    # login command
    subparsers.add_parser("login", help="Open Google sign-in window to authenticate")

    # match command
    match_parser = subparsers.add_parser("match", help="Match tracks without modifying YouTube")
    match_parser.add_argument("url", help="Spotify playlist URL")

    # sync command
    sync_parser = subparsers.add_parser("sync", help="Match tracks and sync to YouTube playlist")
    sync_parser.add_argument("url", help="Spotify playlist URL")
    sync_parser.add_argument("--name", default=None, help="Custom YouTube playlist name")

    args = parser.parse_args()

    if args.command == "web" or len(sys.argv) == 1:
        import run
        run.main()
    elif args.command == "login":
        cli_login()
    elif args.command == "match":
        cli_match(args.url)
    elif args.command == "sync":
        cli_sync(args.url, args.name)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
