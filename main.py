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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Search Spotify for the best matching track on each line of a "
            "YouTube description or any pasted text, then create a playlist."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
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
        "--min-score",
        type=float,
        default=0.45,
        help="Minimum match score from 0 to 1 (default: 0.45)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matches only; do not create a playlist",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    stdin_text = sys.stdin.read() if args.stdin else None
    try:
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
        )
    except RuntimeError as exc:
        logging.error("%s", exc)
        return 1

    print(f"Playlist name: {report.playlist_name}")
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
