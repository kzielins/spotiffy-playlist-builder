"""Playlist ownership and edit operations with a fake Spotify API."""

from __future__ import annotations

import pytest

from spotipy import SpotifyException

from src.auth import DictCacheHandler
from src.parser import LineQuery
from src.pipeline import run_pipeline
from src.parser import SourceText
from src.spotify_client import SpotifyApiError, SpotifyClient, format_retry_wait


class FakeSpotify:
    def __init__(self, user_id: str = "alice") -> None:
        self.user_id = user_id
        self.playlists: dict[str, dict] = {
            "pl1": {
                "id": "pl1",
                "name": "Mine",
                "public": False,
                "owner": {"id": user_id},
                "external_urls": {"spotify": "https://open.spotify.com/playlist/pl1"},
                "tracks": {"total": 1, "items": []},
                "uris": ["spotify:track:old"],
            },
            "other": {
                "id": "other",
                "name": "Someone else",
                "public": True,
                "owner": {"id": "bob"},
                "external_urls": {"spotify": "https://open.spotify.com/playlist/other"},
                "tracks": {"total": 0},
                "uris": [],
            },
        }
        self.created: list[dict] = []
        self.removed: list[list[str]] = []

    def current_user(self) -> dict:
        return {"id": self.user_id, "display_name": "Alice"}

    def current_user_playlists(self, limit: int = 50, offset: int = 0) -> dict:
        items = list(self.playlists.values())[offset : offset + limit]
        return {"items": items, "next": None}

    def playlist(self, playlist_id: str) -> dict:
        return self.playlists[playlist_id]

    def current_user_playlist_create(self, name, public=True, collaborative=False, description=""):
        created = {
            "id": "new1",
            "name": name,
            "public": public,
            "description": description,
            "owner": {"id": self.user_id},
            "external_urls": {"spotify": "https://open.spotify.com/playlist/new1"},
            "tracks": {"total": 0},
            "uris": [],
        }
        self.playlists["new1"] = created
        self.created.append(created)
        return created

    def playlist_add_items(self, playlist_id, items, position=None):
        self.playlists[playlist_id].setdefault("uris", []).extend(items)

    def playlist_replace_items(self, playlist_id, items):
        self.playlists[playlist_id]["uris"] = list(items)

    def playlist_remove_all_occurrences_of_items(self, playlist_id, items, snapshot_id=None):
        self.removed.append(list(items))
        uris = self.playlists[playlist_id].setdefault("uris", [])
        self.playlists[playlist_id]["uris"] = [u for u in uris if u not in items]

    def playlist_change_details(self, playlist_id, name=None, public=None, collaborative=None, description=None):
        pl = self.playlists[playlist_id]
        if name is not None:
            pl["name"] = name
        if public is not None:
            pl["public"] = public
        if description is not None:
            pl["description"] = description

    def search(self, q, type="track", limit=5):
        return {
            "tracks": {
                "items": [
                    {
                        "uri": "spotify:track:hit",
                        "name": q,
                        "popularity": 80,
                        "artists": [{"name": "Artist"}],
                    }
                ]
            }
        }


def _client() -> tuple[SpotifyClient, FakeSpotify]:
    store = {
        "token_info": {
            "access_token": "fake",
            "refresh_token": "fake",
            "expires_at": 9_999_999_999,
            "scope": "playlist-modify-public playlist-modify-private playlist-read-private",
            "expires_in": 3600,
        }
    }
    client = SpotifyClient(
        open_browser=False,
        cache_handler=DictCacheHandler(store),
        use_web_redirect=True,
        search_pace_s=0,
    )
    fake = FakeSpotify()
    client._sp = fake
    return client, fake


def test_list_own_playlists_skips_foreign() -> None:
    client, _ = _client()
    owned = client.list_own_playlists()
    assert [p.id for p in owned] == ["pl1"]


def test_require_owned_playlist_rejects_foreign() -> None:
    client, _ = _client()
    with pytest.raises(RuntimeError, match="only edit playlists you own"):
        client.require_owned_playlist("other")


def test_append_replace_remove_and_update() -> None:
    client, fake = _client()
    client.append_tracks("pl1", ["spotify:track:a"])
    assert "spotify:track:a" in fake.playlists["pl1"]["uris"]
    client.replace_tracks("pl1", ["spotify:track:b"])
    assert fake.playlists["pl1"]["uris"] == ["spotify:track:b"]
    client.remove_tracks("pl1", ["spotify:track:b"])
    assert fake.playlists["pl1"]["uris"] == []
    info = client.update_playlist_details("pl1", name="Renamed", public=True)
    assert info.name == "Renamed"
    assert fake.playlists["pl1"]["public"] is True


def test_pipeline_create_and_append() -> None:
    client, fake = _client()
    source = SourceText(text="Artist - Title")
    _, created = run_pipeline(source, name="Fresh", client=client, dry_run=False)
    assert created.playlist_id == "new1"
    assert fake.created[0]["name"] == "Fresh"
    _, appended = run_pipeline(
        source,
        mode="append",
        playlist_id="pl1",
        client=client,
    )
    assert appended.mode == "append"
    assert "spotify:track:hit" in fake.playlists["pl1"]["uris"]


def test_match_lines_uses_search() -> None:
    client, _ = _client()
    matched, skipped = client.match_lines(
        [LineQuery(raw="x", query="Blinding Lights", kind="free_text")],
        min_score=0.1,
    )
    assert matched and not skipped
    assert matched[0].uri == "spotify:track:hit"


def test_format_retry_wait() -> None:
    assert format_retry_wait(2) == "2 seconds"
    assert format_retry_wait(78689) == "about 22 hours"


def test_early_stop_skips_second_search() -> None:
    client, fake = _client()
    calls: list[str] = []

    def search(q, type="track", limit=5):
        calls.append(q)
        return {
            "tracks": {
                "items": [
                    {
                        "uri": "spotify:track:hit",
                        "name": "Title",
                        "popularity": 100,
                        "artists": [{"name": "Artist"}],
                    }
                ]
            }
        }

    fake.search = search
    client.best_match(
        LineQuery(
            raw="x",
            query="Artist Title",
            kind="artist_title",
            artist="Artist",
            title="Title",
        ),
        min_score=0.1,
    )
    assert len(calls) == 1


def test_short_429_retries_once(monkeypatch) -> None:
    client, fake = _client()
    slept: list[float] = []
    monkeypatch.setattr("src.spotify_client.time.sleep", slept.append)
    n = {"c": 0}

    def search(q, type="track", limit=5):
        n["c"] += 1
        if n["c"] == 1:
            raise SpotifyException(429, -1, "Too many requests", headers={"Retry-After": "2"})
        return {
            "tracks": {
                "items": [
                    {
                        "uri": "spotify:track:hit",
                        "name": "Blinding Lights",
                        "popularity": 80,
                        "artists": [{"name": "The Weeknd"}],
                    }
                ]
            }
        }

    fake.search = search
    matched, _ = client.match_lines(
        [LineQuery(raw="x", query="Blinding Lights", kind="free_text")],
        min_score=0.1,
    )
    assert n["c"] == 2
    assert slept == [2]
    assert matched


def test_long_429_aborts_without_sleeping(monkeypatch) -> None:
    client, fake = _client()
    slept: list[float] = []
    monkeypatch.setattr("src.spotify_client.time.sleep", slept.append)

    def search(q, type="track", limit=5):
        raise SpotifyException(
            429,
            -1,
            "Too many requests",
            headers={"Retry-After": "78689"},
            reason="QUOTA_EXCEEDED",
        )

    fake.search = search
    with pytest.raises(SpotifyApiError, match="about 22 hours"):
        client.match_lines(
            [LineQuery(raw="x", query="Blinding Lights", kind="free_text")],
            min_score=0.1,
        )
    assert slept == []
