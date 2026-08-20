"""Shared CLI / Streamlit pipeline."""

from __future__ import annotations

import logging
from pathlib import Path

from src.parser import (
    LineQuery,
    SourceText,
    extract_queries,
    fetch_youtube_description,
    read_text_file,
    suggest_playlist_name,
)
from src.spotify_client import PlaylistReport, SpotifyClient, clamp_playlist_name

logger = logging.getLogger(__name__)


def load_source(
    *,
    text: str | None = None,
    file_path: str | None = None,
    url: str | None = None,
    stdin_text: str | None = None,
) -> SourceText:
    """Load description text from a URL, file, pasted string, or stdin."""
    if url:
        return fetch_youtube_description(url)
    if file_path:
        path = Path(file_path)
        if file_path == "-":
            raise RuntimeError("Use --stdin to paste text from the terminal")
        return SourceText(text=read_text_file(path))
    body = text if text is not None else stdin_text
    if body is None or not str(body).strip():
        raise RuntimeError("Provide --url, --text, --file, or --stdin")
    return SourceText(text=str(body))


def run_pipeline(
    source: SourceText,
    *,
    name: str | None = None,
    min_score: float = 0.45,
    dry_run: bool = False,
    public: bool = False,
    client: SpotifyClient | None = None,
) -> tuple[list[LineQuery], PlaylistReport]:
    """Parse lines, match Spotify tracks, optionally create a playlist."""
    queries = extract_queries(source.text)
    playlist_name = clamp_playlist_name(
        (name or "").strip()
        or suggest_playlist_name(video_title=source.video_title, queries=queries)
    )
    logger.info("Playlist name: %s", playlist_name)
    sp = client or SpotifyClient()
    matched, skipped = sp.match_lines(queries, min_score=min_score)
    report = PlaylistReport(
        playlist_name=playlist_name,
        matched=matched,
        skipped=skipped,
    )
    if dry_run:
        logger.info("Dry run: %s matched, %s skipped", len(matched), len(skipped))
        return queries, report
    if not matched:
        logger.warning("No tracks matched; playlist was not created")
        return queries, report
    playlist_id, url = sp.create_playlist(
        playlist_name,
        [item.uri for item in matched],
        public=public,
    )
    report.playlist_id = playlist_id
    report.playlist_url = url
    return queries, report
