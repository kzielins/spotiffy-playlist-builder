"""Unit tests for PKCE helpers and isolated token caches."""

from src.auth import DictCacheHandler, new_oauth_state, parse_redirect_params


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
