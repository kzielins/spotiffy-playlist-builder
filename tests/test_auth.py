"""Unit tests for PKCE helpers and isolated token caches."""

from src.auth import (
    DictCacheHandler,
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


def test_parse_redirect_params_error() -> None:
    params = parse_redirect_params("http://127.0.0.1:8501/?error=access_denied")
    assert params["error"] == "access_denied"


def test_oauth_state_is_unique() -> None:
    assert new_oauth_state() != new_oauth_state()


def test_normalize_cloud_and_local_urls() -> None:
    assert (
        normalize_web_redirect_uri("https://spotifyplaylist.streamlit.app")
        == "https://spotifyplaylist.streamlit.app/"
    )
    assert (
        normalize_web_redirect_uri("http://127.0.0.1:8501/?foo=1")
        == "http://127.0.0.1:8501/"
    )


def test_resolve_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "SPOTIFY_WEB_REDIRECT_URI", "https://spotifyplaylist.streamlit.app"
    )
    assert (
        resolve_web_redirect_uri("http://127.0.0.1:8501/")
        == "https://spotifyplaylist.streamlit.app/"
    )


def test_resolve_ignores_loopback_env_on_cloud(monkeypatch) -> None:
    monkeypatch.setenv("SPOTIFY_WEB_REDIRECT_URI", "http://127.0.0.1:8501/")
    assert (
        resolve_web_redirect_uri("https://spotifyplaylist.streamlit.app")
        == "https://spotifyplaylist.streamlit.app/"
    )
