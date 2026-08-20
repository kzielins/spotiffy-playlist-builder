"""PKCE OAuth helpers. End users never need a Client Secret."""

from __future__ import annotations

import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, MutableMapping
from urllib.parse import parse_qs, urlparse, urlunparse

from dotenv import load_dotenv
from spotipy.cache_handler import CacheFileHandler, CacheHandler
from spotipy.oauth2 import SpotifyPKCE

logger = logging.getLogger(__name__)

SCOPES = "playlist-modify-public playlist-modify-private playlist-read-private"
CACHE_PATH = ".cache-spotiffy"
CLI_REDIRECT_URI = "http://127.0.0.1:8888/callback"
WEB_REDIRECT_URI = "http://127.0.0.1:8501/"
# Public Client ID of this project. Override with SPOTIFY_CLIENT_ID.
DEFAULT_CLIENT_ID = "177a447eabb2440988d764fa9f20ad66"


class DictCacheHandler(CacheHandler):
    """Token cache backed by an in-memory mapping (one Streamlit session)."""

    def __init__(self, store: MutableMapping[str, Any], key: str = "token_info") -> None:
        self.store = store
        self.key = key

    def get_cached_token(self) -> dict | None:
        token = self.store.get(self.key)
        return token if isinstance(token, dict) else None

    def save_token_to_cache(self, token_info: dict) -> None:
        self.store[self.key] = token_info

    def clear(self) -> None:
        self.store.pop(self.key, None)


@dataclass
class PendingAuth:
    """PKCE handshake waiting for Spotify's redirect."""

    state: str
    verifier: str
    challenge: str
    redirect_uri: str
    created_at: float = field(default_factory=time.time)


class PendingAuthStore:
    """Handshakes waiting for the Spotify redirect; survives page reloads."""

    def __init__(
        self,
        store: MutableMapping[str, PendingAuth] | None = None,
        ttl: float = 600.0,
    ) -> None:
        self._store: MutableMapping[str, PendingAuth] = store if store is not None else {}
        self.ttl = ttl

    def _purge(self, now: float | None = None) -> None:
        moment = time.time() if now is None else now
        expired = [
            key
            for key, pending in self._store.items()
            if moment - pending.created_at > self.ttl
        ]
        for key in expired:
            self._store.pop(key, None)

    def register(self, pending: PendingAuth) -> None:
        self._purge()
        self._store[pending.state] = pending

    def consume(self, state: str) -> PendingAuth | None:
        """Pop a still-valid handshake. Unknown or expired state returns None."""
        self._purge()
        if not state:
            return None
        pending = self._store.pop(state, None)
        if pending is None:
            return None
        if time.time() - pending.created_at > self.ttl:
            return None
        return pending


def load_client_id() -> str:
    load_dotenv()
    return os.getenv("SPOTIFY_CLIENT_ID", "").strip() or DEFAULT_CLIENT_ID


def cli_redirect_uri() -> str:
    load_dotenv()
    return os.getenv("SPOTIFY_REDIRECT_URI", CLI_REDIRECT_URI).strip() or CLI_REDIRECT_URI


def web_redirect_uri() -> str:
    return resolve_web_redirect_uri()


def normalize_web_redirect_uri(url: str) -> str:
    """Keep scheme, host, and path. Drop query/fragment. Add a trailing slash for directories."""
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid redirect URI: {url!r}")
    path = parsed.path or "/"
    leaf = path.rsplit("/", 1)[-1]
    looks_like_file = bool(leaf) and "." in leaf
    if not looks_like_file and not path.endswith("/"):
        path = f"{path}/"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def resolve_web_redirect_uri(current_url: str | None = None) -> str:
    """Env override, then the live Streamlit URL, then the local default.

    A loopback env value is ignored when the browser is on a public host so
    Streamlit Cloud is not stuck with http://127.0.0.1:8501/.
    """
    load_dotenv()
    explicit = os.getenv("SPOTIFY_WEB_REDIRECT_URI", "").strip()
    detected = ""
    if current_url and current_url.strip():
        detected = normalize_web_redirect_uri(current_url)
    if explicit:
        normalized = normalize_web_redirect_uri(explicit)
        if detected:
            env_host = (urlparse(normalized).hostname or "").lower()
            live_host = (urlparse(detected).hostname or "").lower()
            if env_host in {"127.0.0.1", "localhost"} and live_host not in {
                "127.0.0.1",
                "localhost",
            }:
                return detected
        return normalized
    if detected:
        return detected
    return WEB_REDIRECT_URI


def build_pkce(
    *,
    redirect_uri: str,
    cache_handler: CacheHandler,
    open_browser: bool = True,
    state: str | None = None,
) -> SpotifyPKCE:
    """Authorization Code + PKCE. No client secret is sent."""
    return SpotifyPKCE(
        client_id=load_client_id(),
        redirect_uri=redirect_uri,
        scope=SCOPES,
        open_browser=open_browser,
        cache_handler=cache_handler,
        state=state,
    )


def file_cache_handler(cache_path: str = CACHE_PATH) -> CacheFileHandler:
    return CacheFileHandler(cache_path=cache_path)


def new_oauth_state() -> str:
    return secrets.token_urlsafe(24)


def parse_redirect_params(redirect_response: str) -> dict[str, str]:
    """Read code/state from a full redirect URL or a query string."""
    text = redirect_response.strip()
    if not text:
        return {}
    parsed = urlparse(text if "://" in text or text.startswith("?") else f"?{text}")
    query = parsed.query or (parsed.path if parsed.path.startswith("code=") else "")
    raw = parse_qs(query)
    return {key: values[-1] for key, values in raw.items() if values}


def restore_pkce_handshake(auth: SpotifyPKCE, verifier: str, challenge: str | None) -> None:
    """Reuse the verifier that produced the consent URL (required for PKCE)."""
    auth.code_verifier = verifier
    auth.code_challenge = challenge or auth._get_code_challenge()


def clear_file_token(cache_path: str = CACHE_PATH) -> bool:
    path = Path(cache_path)
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise RuntimeError(f"Could not remove token cache {path}: {exc}") from exc
    logger.info("Removed cached Spotify token %s", path)
    return True
