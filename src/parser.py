"""Normalize mixed text (YouTube descriptions, pasted lists) into search queries."""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

TIMESTAMP_RE = re.compile(
    r"^\s*(?:\[)?(?:\d{1,2}:)?\d{1,2}:\d{2}(?:\.\d+)?(?:\])?\s*[-–—.]?\s*"
)
NUMBERING_RE = re.compile(r"^\s*(?:\d{1,3}[.)]\s*|\d{1,3}\s*[-–—]\s*)")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"@[\w.]+")
HASHTAG_RE = re.compile(r"#\w+")
ARTIST_TITLE_RE = re.compile(r"\s+[-–—]\s+")
NOISE_RE = re.compile(
    r"^(subscribe|follow\s+me|follow\s+us|copyright|tracklist:?|thanks\s+for\s+"
    r"watching|like\s+and\s+subscribe|turn\s+on\s+notifications|link\s+in\s+bio|"
    r"socials?:?|instagram|facebook|twitter|tiktok|discord|merch|stream\s+on)\b",
    re.IGNORECASE,
)


class LineQuery(BaseModel):
    """One candidate line to search on Spotify."""

    raw: str
    query: str
    kind: str = Field(description="artist_title or free_text")
    artist: str | None = None
    title: str | None = None


class SourceText(BaseModel):
    """Loaded description plus optional video title for playlist naming."""

    text: str
    video_title: str | None = None


def clean_line(line: str) -> str:
    """Strip timestamps, numbering, URLs, and social tags from a single line."""
    text = TIMESTAMP_RE.sub("", line)
    text = NUMBERING_RE.sub("", text)
    text = URL_RE.sub("", text)
    text = MENTION_RE.sub("", text)
    text = HASHTAG_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" -–—.|")
    return text.strip()


def is_boilerplate(line: str) -> bool:
    """Return True when the line should never be sent to Spotify search."""
    if not line:
        return True
    if URL_RE.fullmatch(line.strip()) or line.strip().startswith("http"):
        return True
    if HASHTAG_RE.sub("", line).strip() == "":
        return True
    if NOISE_RE.match(line):
        return True
    if len(line) < 2:
        return True
    return False


def classify_query(cleaned: str) -> LineQuery:
    """Mark Artist - Title lines; keep other cleaned lines as free text."""
    parts = ARTIST_TITLE_RE.split(cleaned, maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        artist = parts[0].strip()
        title = parts[1].strip()
        return LineQuery(
            raw=cleaned,
            query=f"{artist} {title}",
            kind="artist_title",
            artist=artist,
            title=title,
        )
    return LineQuery(raw=cleaned, query=cleaned, kind="free_text")


def extract_queries(text: str) -> list[LineQuery]:
    """Turn raw description text into de-duplicated search queries, order preserved."""
    raw_lines = text.splitlines()
    logger.info("Parser received %s raw lines", len(raw_lines))
    candidates: list[LineQuery] = []
    seen: set[str] = set()
    skipped = 0
    for line in raw_lines:
        cleaned = clean_line(line)
        if is_boilerplate(cleaned):
            skipped += 1
            continue
        item = classify_query(cleaned)
        key = item.query.lower()
        if key in seen:
            continue
        seen.add(key)
        candidates.append(item)
    logger.info(
        "Parser kept %s unique candidates (%s boilerplate/empty skipped)",
        len(candidates),
        skipped,
    )
    return candidates


def read_text_file(path: Path) -> str:
    """Read a UTF-8 text file."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Could not read file {path}: {exc}") from exc


def fetch_youtube_description(url: str) -> SourceText:
    """Download video metadata with yt-dlp (no media)."""
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("yt-dlp is required to fetch YouTube descriptions") from exc

    opts: dict[str, object] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
    }
    logger.info("Fetching YouTube description (metadata only)")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # yt-dlp raises many exception types
        raise RuntimeError(f"Could not fetch YouTube metadata: {exc}") from exc

    if not isinstance(info, dict):
        raise RuntimeError("YouTube metadata was empty")
    description = str(info.get("description") or "")
    title = str(info.get("title") or "") or None
    if not description.strip():
        logger.warning("YouTube video has an empty description")
    return SourceText(text=description, video_title=title)


def suggest_playlist_name(
    *,
    video_title: str | None,
    queries: Iterable[LineQuery],
) -> str:
    """Pick a playlist name when the user did not supply one."""
    if video_title:
        name = re.split(r"\s*\|\s*YouTube\s*$", video_title, flags=re.IGNORECASE)[0]
        name = name.strip()
        if name:
            return name[:200]
    query_list = list(queries)
    if query_list:
        first = query_list[0].raw[:80].strip()
        if first:
            return first
    today = date.today().isoformat()
    return f"Spotiffy mix {today}"
