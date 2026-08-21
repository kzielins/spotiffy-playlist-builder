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
from src.spotify_client import (
    PlaylistMode,
    PlaylistReport,
    SpotifyClient,
    clamp_playlist_name,
)

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
    source: SourceText | None,
    *,
    name: str | None = None,
    min_score: float = 0.45,
    dry_run: bool = False,
    public: bool | None = False,
    description: str | None = None,
    mode: PlaylistMode = "create",
    playlist_id: str | None = None,
    client: SpotifyClient | None = None,
    on_progress=None,
) -> tuple[list[LineQuery], PlaylistReport]:
    """Parse lines, match Spotify tracks, then create or edit a playlist."""
    queries: list[LineQuery] = []
    matched = []
    skipped = []
    sp = client or SpotifyClient()

    if mode != "update":
        if source is None:
            raise RuntimeError("Provide a YouTube URL, description, or track list")
        queries = extract_queries(source.text)
        matched, skipped = sp.match_lines(
            queries, min_score=min_score, on_progress=on_progress
        )

    playlist_name = ""
    if mode == "create":
        playlist_name = clamp_playlist_name(
            (name or "").strip()
            or suggest_playlist_name(
                video_title=source.video_title if source else None,
                queries=queries,
            )
        )
    elif playlist_id:
        current = sp.require_owned_playlist(playlist_id)
        playlist_name = (name or "").strip() or str(current.get("name") or "")
    if name and mode != "create":
        playlist_name = clamp_playlist_name(name)

    logger.info("Playlist %s: %s", mode, playlist_name or playlist_id)
    report = PlaylistReport(
        playlist_name=playlist_name or "(unchanged)",
        matched=matched,
        skipped=skipped,
        mode=mode,
        playlist_id=playlist_id,
    )
    if dry_run:
        logger.info("Dry run: %s matched, %s skipped", len(matched), len(skipped))
        return queries, report

    desc = description if description is not None else "Created by Spotiffy playlist builder"
    is_public = False if public is None and mode == "create" else public

    if mode == "create":
        if not matched:
            logger.warning("No tracks matched; playlist was not created")
            return queries, report
        playlist_id, url = sp.create_playlist(
            playlist_name,
            [item.uri for item in matched],
            description=desc,
            public=bool(is_public),
        )
        report.playlist_id = playlist_id
        report.playlist_url = url
        return queries, report

    if not playlist_id:
        raise RuntimeError("--playlist-id is required for append, replace, remove, and update")

    info = None
    uris = [item.uri for item in matched]
    if mode == "append":
        if not uris:
            raise RuntimeError("No tracks matched; nothing was added")
        info = sp.append_tracks(playlist_id, uris)
    elif mode == "replace":
        if not uris:
            raise RuntimeError("No tracks matched; playlist was not replaced")
        info = sp.replace_tracks(playlist_id, uris)
    elif mode == "remove":
        if not uris:
            raise RuntimeError("No tracks matched; nothing was removed")
        info = sp.remove_tracks(playlist_id, uris)
    elif mode == "update":
        if name is None and description is None and public is None:
            raise RuntimeError("Provide --name, --description, and/or --public/--private")
        info = sp.update_playlist_details(
            playlist_id,
            name=name,
            description=description,
            public=public,
        )
    else:
        raise RuntimeError(f"Unknown mode: {mode}")

    if info:
        report.playlist_id = info.id
        report.playlist_url = info.url
        report.playlist_name = info.name
    return queries, report
