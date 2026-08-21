"""Unit tests for PKCE helpers and isolated token caches."""

from src.auth import (
    CLOUD_APP_URL,
    DictCacheHandler,
    PendingAuth,
    PendingAuthStore,
    WEB_REDIRECT_URI,
    new_oauth_state,
    normalize_web_redirect_uri,
    parse_redirect_params,
    resolve_web_redirect_uri,
)


def test_dict_cache_isolation() -> None:
    session_a: dict = {}
    session_b: dict = {}
    a = DictCacheHandler(session_a)
    b = DictCacheHandler(session_b)
    a.save_token_to_cache({"access_token": "aaa", "scope": "playlist-modify-private"})
    assert b.get_cached_token() is None
    assert a.get_cached_token()["access_token"] == "aaa"
    a.clear()
    assert a.get_cached_token() is None


def test_parse_redirect_params_from_url() -> None:
    params = parse_redirect_params(
        "http://127.0.0.1:8501/?code=abc123&state=xyz"
    )
    assert params["code"] == "abc123"
    assert params["state"] == "xyz"


def test_parse_redirect_params_from_cloud_callback() -> None:
    params = parse_redirect_params(
        f"{CLOUD_APP_URL}?code=cloudCode&state=cloudState"
    )
    assert params["code"] == "cloudCode"
    assert params["state"] == "cloudState"
    assert CLOUD_APP_URL == "https://spotifyplaylist.streamlit.app/"
    assert normalize_web_redirect_uri(
        f"{CLOUD_APP_URL.rstrip('/')}/?code=cloudCode&state=cloudState"
    ) == CLOUD_APP_URL


def test_parse_redirect_params_error() -> None:
    params = parse_redirect_params("http://127.0.0.1:8501/?error=access_denied")
    assert params["error"] == "access_denied"


def test_oauth_state_is_unique() -> None:
    assert new_oauth_state() != new_oauth_state()


def test_normalize_cloud_and_local_urls() -> None:
    assert normalize_web_redirect_uri(CLOUD_APP_URL.rstrip("/")) == CLOUD_APP_URL
    assert (
        normalize_web_redirect_uri("http://127.0.0.1:8501/?foo=1")
        == WEB_REDIRECT_URI
    )


def test_resolve_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv("SPOTIFY_WEB_REDIRECT_URI", CLOUD_APP_URL.rstrip("/"))
    assert resolve_web_redirect_uri(WEB_REDIRECT_URI) == CLOUD_APP_URL


def test_resolve_ignores_loopback_env_on_cloud(monkeypatch) -> None:
    monkeypatch.setenv("SPOTIFY_WEB_REDIRECT_URI", WEB_REDIRECT_URI)
    assert resolve_web_redirect_uri(CLOUD_APP_URL.rstrip("/")) == CLOUD_APP_URL


def test_resolve_cloud_callback_url_drops_oauth_query() -> None:
    live = f"{CLOUD_APP_URL}?code=abc&state=xyz"
    assert resolve_web_redirect_uri(live) == CLOUD_APP_URL


def _pending(
    state: str = "s1",
    created_at: float | None = None,
    redirect_uri: str = WEB_REDIRECT_URI,
) -> PendingAuth:
    kwargs: dict = {
        "state": state,
        "verifier": "verifier",
        "challenge": "challenge",
        "redirect_uri": redirect_uri,
    }
    if created_at is not None:
        kwargs["created_at"] = created_at
    return PendingAuth(**kwargs)


def test_pending_store_register_and_consume() -> None:
    store = PendingAuthStore({})
    store.register(_pending("s1"))
    got = store.consume("s1")
    assert got is not None
    assert got.verifier == "verifier"
    assert got.redirect_uri == WEB_REDIRECT_URI


def test_pending_store_consume_is_single_use() -> None:
    store = PendingAuthStore({})
    store.register(_pending("s1"))
    assert store.consume("s1") is not None
    assert store.consume("s1") is None


def test_pending_store_unknown_state() -> None:
    store = PendingAuthStore({})
    store.register(_pending("s1"))
    assert store.consume("missing") is None
    assert store.consume("") is None
    assert store.consume("s1") is not None


def test_pending_store_cloud_redirect_uri() -> None:
    store = PendingAuthStore({})
    store.register(_pending("cloud", redirect_uri=CLOUD_APP_URL))
    got = store.consume("cloud")
    assert got is not None
    assert got.redirect_uri == CLOUD_APP_URL


def test_pending_store_expired_ttl() -> None:
    store = PendingAuthStore({}, ttl=10.0)
    store.register(_pending("old", created_at=0.0))
    store.register(_pending("fresh"))
    assert store.consume("old") is None
    assert store.consume("fresh") is not None
