"""Spotify PKCE client: search, create, and edit playlists."""

from __future__ import annotations

import logging
import re
import time
from difflib import SequenceMatcher
from typing import Iterable, Literal

from pydantic import BaseModel, Field
from spotipy import Spotify, SpotifyException
from spotipy.cache_handler import CacheHandler
from spotipy.oauth2 import SpotifyOauthError, SpotifyPKCE, SpotifyStateError

from src.auth import (
    CACHE_PATH,
    SCOPES,
    DictCacheHandler,
    build_pkce,
    clear_file_token,
    cli_redirect_uri,
    file_cache_handler,
    parse_redirect_params,
    restore_pkce_handshake,
    web_redirect_uri,
)
from src.parser import LineQuery

logger = logging.getLogger(__name__)

BATCH_SIZE = 100
NAME_MAX_LEN = 100
PAREN_RE = re.compile(r"\([^)]*\)|\[[^\]]*\]")
EXTRA_RE = re.compile(
    r"\b(feat\.?|ft\.?|featuring|remix|official|video|audio|lyrics?|hd|4k)\b",
    re.IGNORECASE,
)

PlaylistMode = Literal["create", "append", "replace", "remove", "update"]


class MatchedTrack(BaseModel):
    query: str
    artist: str
    title: str
    uri: str
    score: float


class SkippedLine(BaseModel):
    query: str
    reason: str


class PlaylistInfo(BaseModel):
    id: str
    name: str
    url: str = ""
    public: bool | None = None
    track_count: int = 0
    owner_id: str = ""


class PlaylistReport(BaseModel):
    playlist_name: str
    playlist_url: str | None = None
    playlist_id: str | None = None
    mode: str = "create"
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
            "hint: 403 usually means this Spotify account is not on the app "
            "allowlist (Development Mode, max 5 users) or the token is missing "
            "playlist-modify-* scopes. The owner must add your Spotify e-mail "
            "under Dashboard → User Management. See docs/oauth-login.md."
        )
    return "\n".join(lines)


def clamp_playlist_name(name: str) -> str:
    """Collapse whitespace and clamp to Spotify's 100-character limit."""
    collapsed = re.sub(r"\s+", " ", name).strip()
    if not collapsed:
        raise ValueError("Playlist name is empty")
    return collapsed[:NAME_MAX_LEN].strip()


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
    overlap = (len(q_tokens & l_tokens) / len(q_tokens)) if q_tokens else 0.0
    popularity = float(item.get("popularity") or 0) / 100.0
    return (0.6 * similarity) + (0.3 * overlap) + (0.1 * popularity)


def clear_cached_token(cache_path: str = CACHE_PATH) -> bool:
    return clear_file_token(cache_path)


class SpotifyClient:
    """Thin wrapper around Spotipy with per-line best-match search."""

    def __init__(
        self,
        *,
        open_browser: bool = True,
        cache_path: str = CACHE_PATH,
        cache_handler: CacheHandler | None = None,
        redirect_uri: str | None = None,
        state: str | None = None,
        use_web_redirect: bool = False,
        auth: SpotifyPKCE | None = None,
    ) -> None:
        if auth is not None:
            self._auth = auth
        else:
            handler = cache_handler or file_cache_handler(cache_path)
            uri = redirect_uri or (
                web_redirect_uri() if use_web_redirect else cli_redirect_uri()
            )
            self._auth = build_pkce(
                redirect_uri=uri,
                cache_handler=handler,
                open_browser=open_browser,
                state=state,
            )
        self._redirect_uri = self._auth.redirect_uri
        self._cache_path = cache_path
        self._sp = Spotify(auth_manager=self._auth)

    def authorize_url(self, state: str | None = None) -> str:
        """Consent URL. Store code_verifier before the user leaves the page."""
        return self._auth.get_authorize_url(state=state)

    def pkce_handshake(self) -> tuple[str, str]:
        if not self._auth.code_verifier:
            self._auth.get_pkce_handshake_parameters()
        return str(self._auth.code_verifier), str(self._auth.code_challenge)

    def restore_handshake(self, verifier: str, challenge: str | None) -> None:
        restore_pkce_handshake(self._auth, verifier, challenge)

    def has_cached_token(self) -> bool:
        return bool(self._auth.cache_handler.get_cached_token())

    def complete_auth(self, redirect_response: str, *, expected_state: str | None = None) -> None:
        """Exchange the ?code= from a redirect URL for a cached token."""
        params = parse_redirect_params(redirect_response)
        if params.get("error"):
            raise RuntimeError(f"Spotify denied access: {params['error']}")
        code = params.get("code") or self._auth.parse_response_code(redirect_response.strip())
        if not code or code == redirect_response.strip():
            raise RuntimeError(
                "No ?code= parameter found. Copy the whole address bar after "
                "approving access, or open the app from the Spotify redirect."
            )
        returned_state = params.get("state")
        expected = expected_state if expected_state is not None else self._auth.state
        if expected and returned_state and returned_state != expected:
            raise RuntimeError("OAuth state mismatch; start sign-in again.")
        if not self._auth.code_verifier:
            raise RuntimeError(
                "PKCE verifier is missing. Start sign-in from this same browser "
                "session so the consent URL and callback stay paired."
            )
        try:
            self._auth.get_access_token(code, check_cache=False)
        except SpotifyStateError as exc:
            raise RuntimeError("OAuth state mismatch; start sign-in again.") from exc
        except SpotifyOauthError as exc:
            raise RuntimeError(f"Could not exchange the OAuth code: {exc}") from exc
        except SpotifyException as exc:
            details = describe_spotify_error(exc, action="POST /api/token")
            logger.error("Token exchange failed\n%s", details)
            raise SpotifyApiError("Could not exchange the OAuth code", details) from exc
        logger.info("Stored a fresh Spotify user token (PKCE)")

    def sign_out(self) -> bool:
        handler = self._auth.cache_handler
        if isinstance(handler, DictCacheHandler):
            had = bool(handler.get_cached_token())
            handler.clear()
            return had
        return clear_file_token(self._cache_path)

    def granted_scopes(self) -> list[str]:
        token = self._auth.cache_handler.get_cached_token() or {}
        return sorted(str(token.get("scope") or "").split())

    def auth_status(self) -> dict[str, object]:
        """Report the signed-in account and granted scopes (never the token)."""
        granted = self.granted_scopes()
        cached = self.has_cached_token()
        status: dict[str, object] = {
            "redirect_uri": self._redirect_uri,
            "token_cache": self._cache_path,
            "cached_token": cached,
            "connected": False,
            "granted_scopes": granted,
            "missing_scopes": sorted(set(SCOPES.split()) - set(granted)),
            "user_id": "",
            "display_name": "",
            "product": "unknown",
            "country": "unknown",
        }
        if not cached:
            return status
        try:
            me = self._sp.current_user() or {}
        except SpotifyException as exc:
            details = describe_spotify_error(exc, action="GET /v1/me")
            logger.error("Spotify auth check failed\n%s", details)
            raise SpotifyApiError("Spotify authentication failed", details) from exc
        except EOFError as exc:
            raise RuntimeError(
                "Spotify asked for interactive consent, which is not possible here. "
                "Sign in again from the app or run `python main.py --check-auth`."
            ) from exc
        status["connected"] = True
        status["user_id"] = str(me.get("id") or "")
        status["display_name"] = str(me.get("display_name") or "")
        status["product"] = str(me.get("product") or "unknown")
        status["country"] = str(me.get("country") or "unknown")
        return status

    def current_user_id(self) -> str:
        try:
            me = self._sp.current_user() or {}
        except SpotifyException as exc:
            details = describe_spotify_error(exc, action="GET /v1/me")
            raise SpotifyApiError("Could not read the Spotify account", details) from exc
        user_id = str(me.get("id") or "")
        if not user_id:
            raise RuntimeError("Spotify returned an empty user id")
        return user_id

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

    def list_own_playlists(self) -> list[PlaylistInfo]:
        user_id = self.current_user_id()
        playlists: list[PlaylistInfo] = []
        offset = 0
        while True:
            try:
                page = self._sp.current_user_playlists(limit=50, offset=offset) or {}
            except SpotifyException as exc:
                details = describe_spotify_error(exc, action="GET /v1/me/playlists")
                raise SpotifyApiError("Could not list playlists", details) from exc
            items = page.get("items") or []
            for raw in items:
                owner = (raw.get("owner") or {}).get("id") or ""
                if owner != user_id:
                    continue
                playlists.append(_playlist_info(raw, owner_id=user_id))
            if not page.get("next") or not items:
                break
            offset += len(items)
        return playlists

    def require_owned_playlist(self, playlist_id: str) -> dict:
        try:
            playlist = self._sp.playlist(playlist_id) or {}
        except SpotifyException as exc:
            details = describe_spotify_error(
                exc, action=f"GET /v1/playlists/{playlist_id}"
            )
            raise SpotifyApiError("Could not load playlist", details) from exc
        owner = str((playlist.get("owner") or {}).get("id") or "")
        if owner != self.current_user_id():
            raise RuntimeError("You can only edit playlists you own")
        return playlist

    def update_playlist_details(
        self,
        playlist_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        public: bool | None = None,
    ) -> PlaylistInfo:
        playlist = self.require_owned_playlist(playlist_id)
        kwargs: dict[str, object] = {}
        if name is not None:
            kwargs["name"] = clamp_playlist_name(name)
        if description is not None:
            kwargs["description"] = description
        if public is not None:
            kwargs["public"] = public
        if kwargs:
            try:
                self._sp.playlist_change_details(playlist_id, **kwargs)
            except SpotifyException as exc:
                details = describe_spotify_error(
                    exc, action=f"PUT /v1/playlists/{playlist_id}"
                )
                raise SpotifyApiError("Could not update playlist details", details) from exc
            playlist.update(kwargs)
        return _playlist_info(playlist, owner_id=str((playlist.get("owner") or {}).get("id") or ""))

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
        self._add_uris(playlist_id, uris)
        logger.info("Created playlist %s with %s tracks", playlist_name, len(uris))
        return playlist_id, str(url or "")

    def append_tracks(self, playlist_id: str, uris: list[str]) -> PlaylistInfo:
        playlist = self.require_owned_playlist(playlist_id)
        self._add_uris(playlist_id, uris)
        return _playlist_info(playlist)

    def replace_tracks(self, playlist_id: str, uris: list[str]) -> PlaylistInfo:
        playlist = self.require_owned_playlist(playlist_id)
        first, rest = uris[:BATCH_SIZE], uris[BATCH_SIZE:]
        try:
            self._sp.playlist_replace_items(playlist_id, first)
        except SpotifyException as exc:
            details = describe_spotify_error(
                exc, action=f"PUT /v1/playlists/{playlist_id}/items"
            )
            raise SpotifyApiError("Could not replace playlist tracks", details) from exc
        if rest:
            self._add_uris(playlist_id, rest)
        return _playlist_info(playlist)

    def remove_tracks(self, playlist_id: str, uris: list[str]) -> PlaylistInfo:
        playlist = self.require_owned_playlist(playlist_id)
        unique = list(dict.fromkeys(uris))
        for i in range(0, len(unique), BATCH_SIZE):
            chunk = unique[i : i + BATCH_SIZE]
            try:
                self._sp.playlist_remove_all_occurrences_of_items(playlist_id, chunk)
            except SpotifyException as exc:
                details = describe_spotify_error(
                    exc, action=f"DELETE /v1/playlists/{playlist_id}/items"
                )
                raise SpotifyApiError("Could not remove tracks", details) from exc
        return _playlist_info(playlist)

    def _add_uris(self, playlist_id: str, uris: list[str]) -> None:
        for i in range(0, len(uris), BATCH_SIZE):
            chunk = uris[i : i + BATCH_SIZE]
            try:
                self._sp.playlist_add_items(playlist_id, chunk)
            except SpotifyException as exc:
                details = describe_spotify_error(
                    exc, action=f"POST /v1/playlists/{playlist_id}/items"
                )
                logger.error("Adding tracks failed\n%s", details)
                raise SpotifyApiError(
                    f"Could not add tracks to playlist (HTTP {exc.http_status})",
                    details,
                ) from exc


def _playlist_info(raw: dict, owner_id: str = "") -> PlaylistInfo:
    return PlaylistInfo(
        id=str(raw.get("id") or ""),
        name=str(raw.get("name") or ""),
        url=str((raw.get("external_urls") or {}).get("spotify") or ""),
        public=raw.get("public"),
        track_count=int((raw.get("tracks") or {}).get("total") or 0),
        owner_id=owner_id or str((raw.get("owner") or {}).get("id") or ""),
    )
