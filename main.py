#!/usr/bin/env python3
"""CLI: YouTube description or pasted text → Spotify playlist."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline import load_source, run_pipeline
from src.spotify_client import (
    PlaylistMode,
    SpotifyApiError,
    SpotifyClient,
    clear_cached_token,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Search Spotify for the best matching track on each line of a "
            "YouTube description or any pasted text, then create or edit a playlist. "
            "Sign in with Spotify in the browser; no Client Secret is required."
        )
    )
    source = parser.add_mutually_exclusive_group(required=False)
    source.add_argument("--url", help="YouTube video URL (description via yt-dlp)")
    source.add_argument("--text", help="Pasted description or mixed track list")
    source.add_argument("--file", help="Path to a UTF-8 .txt file")
    source.add_argument(
        "--stdin",
        action="store_true",
        help="Read multi-line text from stdin (end with Ctrl-D)",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Playlist name (optional; a title is suggested when omitted)",
    )
    parser.add_argument(
        "--description",
        default=None,
        help="Playlist description (create/update)",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.45,
        help="Minimum match score from 0 to 1 (default: 0.45)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matches only; do not create or edit a playlist",
    )
    visibility = parser.add_mutually_exclusive_group()
    visibility.add_argument(
        "--public",
        action="store_true",
        help="Make the playlist public (create default: private)",
    )
    visibility.add_argument(
        "--private",
        action="store_true",
        help="Make the playlist private",
    )
    parser.add_argument(
        "--mode",
        choices=["create", "append", "replace", "remove", "update"],
        default="create",
        help="create (default), append, replace, remove, or update details",
    )
    parser.add_argument(
        "--playlist-id",
        default=None,
        help="Existing playlist id (required except for --mode create)",
    )
    parser.add_argument(
        "--list-playlists",
        action="store_true",
        help="List playlists you own, then exit",
    )
    parser.add_argument(
        "--check-auth",
        action="store_true",
        help="Show the signed-in Spotify account and granted scopes, then exit",
    )
    parser.add_argument(
        "--relogin",
        action="store_true",
        help="Delete the cached token and re-run the OAuth consent flow",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging",
    )
    return parser


def visibility_flag(args: argparse.Namespace) -> bool | None:
    if args.public:
        return True
    if args.private:
        return False
    if args.mode == "create":
        return False
    return None


def print_auth_status() -> int:
    """Print the account and scopes behind the cached token."""
    try:
        status = SpotifyClient().auth_status()
    except SpotifyApiError as exc:
        print(f"Auth check failed: {exc}")
        print(exc.details)
        return 1
    except RuntimeError as exc:
        print(f"Auth check failed: {exc}")
        return 1
    if not status["connected"]:
        print(f"Not connected. No cached token in {status['token_cache']}.")
        print(f"Redirect URI:    {status['redirect_uri']}")
        print("Run any search command to open the Spotify consent screen.")
        return 1
    print(f"Spotify user:    {status['user_id']} ({status['display_name']})")
    print(f"Account type:    {status['product']} / {status['country']}")
    print(f"Redirect URI:    {status['redirect_uri']}")
    print(f"Token cache:     {status['token_cache']} (present={status['cached_token']})")
    print(f"Granted scopes:  {' '.join(status['granted_scopes']) or '-'}")
    missing = status["missing_scopes"]
    if missing:
        print(f"MISSING scopes:  {' '.join(missing)}")
        print("Run `python main.py --relogin --check-auth` to re-consent.")
    else:
        print("All required playlist scopes are granted.")
    return 0


def print_playlists() -> int:
    try:
        playlists = SpotifyClient().list_own_playlists()
    except SpotifyApiError as exc:
        print(f"Could not list playlists: {exc}")
        print(exc.details)
        return 1
    except RuntimeError as exc:
        print(f"Could not list playlists: {exc}")
        return 1
    if not playlists:
        print("No owned playlists.")
        return 0
    print(f"{'ID':<24}  {'tracks':>6}  {'vis':<8}  name")
    for item in playlists:
        vis = "public" if item.public else "private"
        print(f"{item.id:<24}  {item.track_count:>6}  {vis:<8}  {item.name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.relogin:
        removed = clear_cached_token()
        print("Cached token removed." if removed else "No cached token found.")
    if args.check_auth:
        return print_auth_status()
    if args.list_playlists:
        return print_playlists()
    mode: PlaylistMode = args.mode
    if mode != "update" and not (args.url or args.text or args.file or args.stdin):
        parser.error("one of --url, --text, --file, --stdin is required")
    if mode != "create" and not args.playlist_id:
        parser.error("--playlist-id is required unless --mode create")

    stdin_text = sys.stdin.read() if args.stdin else None
    try:
        source = None
        if args.url or args.text or args.file or args.stdin:
            source = load_source(
                text=args.text,
                file_path=args.file,
                url=args.url,
                stdin_text=stdin_text,
            )
        _, report = run_pipeline(
            source,
            name=args.name,
            min_score=args.min_score,
            dry_run=args.dry_run,
            public=visibility_flag(args),
            description=args.description,
            mode=mode,
            playlist_id=args.playlist_id,
        )
    except SpotifyApiError as exc:
        logging.error("%s\n%s", exc, exc.details)
        return 1
    except RuntimeError as exc:
        logging.error("%s", exc)
        return 1

    print(f"Mode: {report.mode}")
    print(f"Playlist name: {report.playlist_name}")
    if report.playlist_id:
        print(f"Playlist id: {report.playlist_id}")
    if report.playlist_url:
        print(f"Playlist URL: {report.playlist_url}")
    print(f"Matched: {len(report.matched)}")
    for item in report.matched:
        print(f"  + {item.artist} – {item.title}  ({item.score:.2f})  ← {item.query}")
    print(f"Skipped: {len(report.skipped)}")
    for item in report.skipped:
        print(f"  - {item.query}  ({item.reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
