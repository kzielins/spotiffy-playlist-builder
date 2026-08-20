"""Spotify OAuth client: search each line and create playlists."""

from __future__ import annotations

import logging
import os
import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from spotipy import Spotify, SpotifyException
from spotipy.oauth2 import SpotifyOAuth

from src.parser import LineQuery

logger = logging.getLogger(__name__)

SCOPES = "playlist-modify-public playlist-modify-private"
BATCH_SIZE = 100
CACHE_PATH = ".cache-spotiffy"
NAME_MAX_LEN = 100
PAREN_RE = re.compile(r"\([^)]*\)|\[[^\]]*\]")
EXTRA_RE = re.compile(
    r"\b(feat\.?|ft\.?|featuring|remix|official|video|audio|lyrics?|hd|4k)\b",
    re.IGNORECASE,
)


class MatchedTrack(BaseModel):
    query: str
    artist: str
    title: str
    uri: str
    score: float


class SkippedLine(BaseModel):
    query: str
    reason: str


class PlaylistReport(BaseModel):
    playlist_name: str
    playlist_url: str | None = None
    playlist_id: str | None = None
    matched: list[MatchedTrack] = Field(default_factory=list)
    skipped: list[SkippedLine] = Field(default_factory=list)


class SpotifyApiError(RuntimeError):
    """Spotify call failed; `details` holds the full server response dump."""

    def __init__(self, message: str, details: str = "") -> None:
        super().__init__(message)
        self.details = details


def describe_spotify_error(exc: SpotifyException, *, action: str) -> str:
    """Render everything Spotify returned, without touching credentials."""
    lines = [
        f"action: {action}",
        f"http_status: {exc.http_status}",
        f"api_code: {exc.code}",
        f"reason: {exc.reason or '-'}",
        f"message: {exc.msg}",
    ]
    retry_after = (exc.headers or {}).get("Retry-After") if exc.headers else None
    if retry_after:
        lines.append(f"retry_after: {retry_after}")
    if exc.http_status == 403:
        lines.append(
            "hint: 403 on playlist writes usually means the granted token is "
            "missing playlist-modify-* scopes, or the app is in Development mode "
            "and this Spotify account is not on its user list. "
            "Run `python main.py --check-auth` and see docs/oauth-login.md."
        )
    return "\n".join(lines)


def clear_cached_token(cache_path: str = CACHE_PATH) -> bool:
    """Delete the cached OAuth token so the next run asks for consent again."""
    path = Path(cache_path)
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise RuntimeError(f"Could not remove token cache {path}: {exc}") from exc
    logger.info("Removed cached Spotify token %s", path)
    return True


def clamp_playlist_name(name: str) -> str:
    """Collapse whitespace and clamp to Spotify's 100-character limit."""
    collapsed = re.sub(r"\s+", " ", name).strip()
    if not collapsed:
        raise ValueError("Playlist name is empty")
    return collapsed[:NAME_MAX_LEN].strip()


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing {name}. Copy .env.example to .env and fill in Spotify Dashboard "
            "credentials. See docs/spotify-app-and-tokens.md."
        )
    return value


def simplify_query(text: str) -> str:
    """Drop feat./remix/parenthetical notes for a looser search."""
    cleaned = PAREN_RE.sub(" ", text)
    cleaned = EXTRA_RE.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _track_label(item: dict) -> str:
    artists = ", ".join(a.get("name", "") for a in item.get("artists") or [])
    name = str(item.get("name") or "")
    return f"{artists} {name}".strip()


def score_candidate(query: str, item: dict) -> float:
    """Combine string similarity with a small popularity bonus (0–1)."""
    label = _track_label(item)
    similarity = SequenceMatcher(None, query.lower(), label.lower()).ratio()
    q_tokens = set(query.lower().split())
    l_tokens = set(label.lower().split())
    if q_tokens:
        overlap = len(q_tokens & l_tokens) / len(q_tokens)
    else:
        overlap = 0.0
    popularity = float(item.get("popularity") or 0) / 100.0
    return (0.6 * similarity) + (0.3 * overlap) + (0.1 * popularity)


class SpotifyClient:
    """Thin wrapper around Spotipy with per-line best-match search."""

    def __init__(
        self,
        *,
        open_browser: bool = True,
        cache_path: str = CACHE_PATH,
    ) -> None:
        load_dotenv()
        client_id = _require_env("SPOTIFY_CLIENT_ID")
        client_secret = _require_env("SPOTIFY_CLIENT_SECRET")
        redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
        self._redirect_uri = redirect_uri
        self._cache_path = cache_path
        self._auth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=SCOPES,
            open_browser=open_browser,
            cache_path=cache_path,
        )
        self._sp = Spotify(auth_manager=self._auth)

    def authorize_url(self) -> str:
        """Consent URL to open manually when no browser is available."""
        return self._auth.get_authorize_url()

    def has_cached_token(self) -> bool:
        return bool(self._auth.cache_handler.get_cached_token())

    def complete_auth(self, redirect_response: str) -> None:
        """Exchange the ?code= from a pasted redirect URL for a cached token."""
        response = redirect_response.strip()
        if not response:
            raise RuntimeError("Paste the full redirect URL first")
        code = self._auth.parse_response_code(response)
        if not code or code == response:
            raise RuntimeError(
                "No ?code= parameter found in the pasted URL. Copy the whole "
                "address bar contents after approving access."
            )
        try:
            self._auth.get_access_token(code, as_dict=False, check_cache=False)
        except SpotifyException as exc:
            details = describe_spotify_error(exc, action="POST /api/token")
            logger.error("Token exchange failed\n%s", details)
            raise SpotifyApiError("Could not exchange the OAuth code", details) from exc
        except Exception as exc:  # spotipy wraps requests errors loosely
            raise RuntimeError(f"Could not exchange the OAuth code: {exc}") from exc
        logger.info("Stored a fresh Spotify token in %s", self._cache_path)

    def sign_out(self) -> bool:
        """Drop the cached token for this client."""
        return clear_cached_token(self._cache_path)

    def granted_scopes(self) -> list[str]:
        token = self._auth.cache_handler.get_cached_token() or {}
        return sorted(str(token.get("scope") or "").split())

    def auth_status(self) -> dict[str, object]:
        """Report the signed-in account and granted scopes (never the token)."""
        granted = self.granted_scopes()
        status: dict[str, object] = {
            "redirect_uri": self._redirect_uri,
            "token_cache": self._cache_path,
            "cached_token": self.has_cached_token(),
            "granted_scopes": granted,
            "missing_scopes": sorted(set(SCOPES.split()) - set(granted)),
        }
        try:
            me = self._sp.current_user() or {}
        except SpotifyException as exc:
            details = describe_spotify_error(exc, action="GET /v1/me")
            logger.error("Spotify auth check failed\n%s", details)
            raise SpotifyApiError("Spotify authentication failed", details) from exc
        status["user_id"] = str(me.get("id") or "")
        status["display_name"] = str(me.get("display_name") or "")
        status["product"] = str(me.get("product") or "unknown")
        status["country"] = str(me.get("country") or "unknown")
        return status

    def _search(self, q: str) -> list[dict]:
        if not q.strip():
            return []
        try:
            result = self._sp.search(q=q, type="track", limit=5)
        except SpotifyException as exc:
            logger.warning(
                "Spotify search failed for %r\n%s",
                q,
                describe_spotify_error(exc, action="GET /v1/search"),
            )
            if exc.http_status == 429:
                retry = int(exc.headers.get("Retry-After", 1)) if exc.headers else 1
                time.sleep(min(retry, 5))
                try:
                    result = self._sp.search(q=q, type="track", limit=5)
                except SpotifyException as retry_exc:
                    logger.warning(
                        "Retry failed for %r\n%s",
                        q,
                        describe_spotify_error(retry_exc, action="GET /v1/search retry"),
                    )
                    return []
            else:
                return []
        tracks = (result or {}).get("tracks") or {}
        return list(tracks.get("items") or [])

    def best_match(self, line: LineQuery, min_score: float) -> MatchedTrack | None:
        """Try structured then free-text queries; keep the highest scoring track."""
        attempts: list[str] = []
        if line.kind == "artist_title" and line.artist and line.title:
            attempts.append(f"artist:{line.artist} track:{line.title}")
        simplified = simplify_query(line.query)
        if simplified:
            attempts.append(simplified)
        if line.title:
            attempts.append(simplify_query(line.title) or line.title)
        if line.query not in attempts:
            attempts.append(line.query)

        best_item: dict | None = None
        best_score = 0.0
        seen_uri: set[str] = set()
        for attempt in attempts:
            for item in self._search(attempt):
                uri = str(item.get("uri") or "")
                if not uri or uri in seen_uri:
                    continue
                seen_uri.add(uri)
                score = score_candidate(line.query, item)
                if score > best_score:
                    best_score = score
                    best_item = item

        if best_item is None:
            return None
        if best_score < min_score:
            logger.debug(
                "Rejected %r (score %.2f below %.2f)",
                line.query,
                best_score,
                min_score,
            )
            return None
        artists = ", ".join(
            str(a.get("name") or "") for a in best_item.get("artists") or []
        )
        return MatchedTrack(
            query=line.query,
            artist=artists,
            title=str(best_item.get("name") or ""),
            uri=str(best_item.get("uri") or ""),
            score=round(best_score, 3),
        )

    def match_lines(
        self, lines: Iterable[LineQuery], min_score: float
    ) -> tuple[list[MatchedTrack], list[SkippedLine]]:
        matched: list[MatchedTrack] = []
        skipped: list[SkippedLine] = []
        seen_uris: set[str] = set()
        for line in lines:
            hit = self.best_match(line, min_score=min_score)
            if hit is None:
                skipped.append(SkippedLine(query=line.query, reason="no_confident_match"))
                continue
            if hit.uri in seen_uris:
                skipped.append(SkippedLine(query=line.query, reason="duplicate_track"))
                continue
            seen_uris.add(hit.uri)
            matched.append(hit)
            logger.info(
                "Matched %r → %s – %s (%.2f)",
                line.query,
                hit.artist,
                hit.title,
                hit.score,
            )
        return matched, skipped

    def create_playlist(
        self,
        name: str,
        uris: list[str],
        description: str = "Created by Spotiffy playlist builder",
        public: bool = False,
    ) -> tuple[str, str]:
        """Create a playlist for the current user and add URIs in batches of 100."""
        try:
            playlist_name = clamp_playlist_name(name)
        except ValueError as exc:
            raise RuntimeError(f"Invalid playlist name: {exc}") from exc
        missing = sorted(set(SCOPES.split()) - set(self.granted_scopes()))
        if missing:
            logger.warning(
                "Cached token is missing scopes %s; re-authenticate to fix writes",
                ", ".join(missing),
            )
        try:
            playlist = self._sp.current_user_playlist_create(
                name=playlist_name,
                public=public,
                description=description,
            )
        except SpotifyException as exc:
            details = describe_spotify_error(exc, action="POST /v1/me/playlists")
            logger.error("Playlist creation failed\n%s", details)
            raise SpotifyApiError(
                f"Could not create playlist (HTTP {exc.http_status})", details
            ) from exc
        playlist_id = str((playlist or {}).get("id") or "")
        url = ((playlist or {}).get("external_urls") or {}).get("spotify")
        if not playlist_id:
            raise RuntimeError("Spotify returned a playlist without an id")
        for i in range(0, len(uris), BATCH_SIZE):
            chunk = uris[i : i + BATCH_SIZE]
            try:
                self._sp.playlist_add_items(playlist_id, chunk)
            except SpotifyException as exc:
                details = describe_spotify_error(
                    exc, action=f"POST /v1/playlists/{playlist_id}/tracks"
                )
                logger.error("Adding tracks failed\n%s", details)
                raise SpotifyApiError(
                    f"Could not add tracks to playlist (HTTP {exc.http_status})",
                    details,
                ) from exc
        logger.info("Created playlist %s with %s tracks", playlist_name, len(uris))
        return playlist_id, str(url or "")
