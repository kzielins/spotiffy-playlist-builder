"""Streamlit UI for Spotiffy playlist builder."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.auth import (
    SCOPES,
    DictCacheHandler,
    PendingAuth,
    PendingAuthStore,
    new_oauth_state,
    resolve_web_redirect_uri,
)
from src.parser import suggest_playlist_name
from src.pipeline import load_source, run_pipeline
from src.spotify_client import PlaylistMode, SpotifyApiError, SpotifyClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def show_error(message: str, details: str = "") -> None:
    st.error(message)
    if details:
        with st.expander("Spotify error details"):
            st.code(details)


def current_web_redirect() -> str:
    """Spotify redirect URI for this browser origin (local or Streamlit Cloud)."""
    live = getattr(st.context, "url", None)
    return resolve_web_redirect_uri(live)


@st.cache_resource
def pending_auth_store() -> PendingAuthStore:
    """Process-wide PKCE handshakes. Session state is empty after Spotify redirects."""
    return PendingAuthStore()


def session_client(*, redirect_uri: str | None = None) -> SpotifyClient:
    store = st.session_state.setdefault("spotify_token_store", {})
    uri = redirect_uri or current_web_redirect()
    return SpotifyClient(
        open_browser=False,
        cache_handler=DictCacheHandler(store),
        redirect_uri=uri,
    )


def consume_oauth_callback() -> None:
    params = st.query_params
    if params.get("error"):
        show_error(f"Spotify denied access: {params.get('error')}")
        st.query_params.clear()
        return
    code = params.get("code")
    if not code:
        return
    state = params.get("state") or ""
    pending = pending_auth_store().consume(state)
    if pending is None:
        show_error(
            "Sign-in link expired or was already used. "
            "Click Sign in with Spotify again."
        )
        st.query_params.clear()
        return
    client = session_client(redirect_uri=pending.redirect_uri)
    client.restore_handshake(pending.verifier, pending.challenge)
    redirect = f"{pending.redirect_uri}?code={code}"
    if pending.state:
        redirect += f"&state={pending.state}"
    try:
        client.complete_auth(redirect, expected_state=pending.state)
    except SpotifyApiError as exc:
        show_error(str(exc), exc.details)
        return
    except RuntimeError as exc:
        show_error(str(exc))
        return
    st.query_params.clear()
    st.success("Spotify connected.")
    st.rerun()


def render_login(client: SpotifyClient) -> None:
    state = new_oauth_state()
    verifier, challenge = client.pkce_handshake()
    redirect_uri = current_web_redirect()
    pending_auth_store().register(
        PendingAuth(
            state=state,
            verifier=verifier,
            challenge=challenge,
            redirect_uri=redirect_uri,
        )
    )
    url = client.authorize_url(state)
    st.warning("Sign in with Spotify to search tracks and edit your playlists.")
    st.markdown(f"[Sign in with Spotify]({url})")
    st.caption(f"OAuth redirect URI: `{redirect_uri}`")
    st.caption(
        "You will be asked to allow playlist access. After Spotify sends you back "
        "here, this page finishes login automatically. The Sign in link is "
        "single-use and expires after a few minutes — do not bookmark it. "
        "Development Mode apps work for up to 5 allowlisted accounts. The "
        "redirect URI above must be listed exactly in the Spotify Dashboard."
    )


def render_sidebar(client: SpotifyClient) -> None:
    with st.sidebar:
        st.subheader("Spotify account")
        if client.has_cached_token():
            try:
                status = client.auth_status()
            except SpotifyApiError as exc:
                show_error(str(exc), exc.details)
                return
            except RuntimeError as exc:
                show_error(str(exc))
                return
            if status["connected"]:
                st.write(f"User: `{status['user_id']}`")
                st.write(f"Name: {status['display_name'] or '-'}")
                st.write(f"Scopes: `{' '.join(status['granted_scopes']) or '-'}`")
                missing = status["missing_scopes"]
                if missing:
                    st.error(f"Missing scopes: {' '.join(missing)}")
                    st.caption(
                        "Log out and sign in again so Spotify can grant "
                        "playlist-read-private (needed to list playlists)."
                    )
                    if st.button("Sign in again for playlist access"):
                        client.sign_out()
                        st.session_state.pop("owned_playlists", None)
                        st.rerun()
                else:
                    st.success("Playlist scopes granted.")
            else:
                st.warning("Not connected.")
        else:
            st.info("Not signed in.")
        if st.button("Log out"):
            client.sign_out()
            st.session_state.pop("owned_playlists", None)
            st.rerun()


def report_tables(report) -> None:
    st.success(f"{report.mode}: {report.playlist_name}")
    if report.playlist_url:
        st.markdown(f"[Open in Spotify]({report.playlist_url})")
    st.subheader("Matched")
    if report.matched:
        st.dataframe(
            [
                {
                    "line": m.query,
                    "artist": m.artist,
                    "title": m.title,
                    "score": m.score,
                }
                for m in report.matched
            ],
            width="stretch",
        )
    else:
        st.write("No confident matches.")
    st.subheader("Skipped")
    if report.skipped:
        st.dataframe(
            [{"line": s.query, "reason": s.reason} for s in report.skipped],
            width="stretch",
        )
    else:
        st.write("Nothing skipped.")


def main() -> None:
    st.set_page_config(page_title="Spotiffy playlist builder", layout="centered")
    st.title("YouTube description → Spotify playlist")
    consume_oauth_callback()
    client = session_client()
    render_sidebar(client)
    if not client.has_cached_token():
        render_login(client)
        return

    st.write(
        "Paste a YouTube URL **or** any description / mixed text. "
        "Each line is searched on Spotify. You can create a new playlist or "
        "edit one you already own."
    )
    url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
    description = st.text_area(
        "Description or track list",
        height=220,
        placeholder="00:00 Artist - Title\nThanks for watching\nBlinding Lights",
    )
    name = st.text_input(
        "Playlist name (optional)",
        placeholder="Suggested from the video title or first line",
    )
    playlist_description = st.text_input("Playlist description (optional)")
    min_score = st.slider("Minimum match score", 0.0, 1.0, 0.45, 0.05)
    public = st.checkbox("Public playlist", value=False)
    dry_run = st.checkbox("Dry run (search only, do not change Spotify)")

    target = st.radio("Target", ["Create new playlist", "Edit existing playlist"])
    mode: PlaylistMode = "create"
    playlist_id: str | None = None
    if target == "Edit existing playlist":
        if "playlist-read-private" in set(SCOPES.split()) - set(client.granted_scopes()):
            st.error(
                "This session cannot list playlists (missing playlist-read-private). "
                "Use **Sign in again for playlist access** in the sidebar."
            )
            return
        refresh = st.button("Refresh playlist list")
        if refresh:
            st.session_state.pop("owned_playlists", None)
        try:
            if "owned_playlists" not in st.session_state:
                st.session_state.owned_playlists = client.list_own_playlists()
            owned = st.session_state.owned_playlists
        except SpotifyApiError as exc:
            show_error(str(exc), exc.details)
            return
        if not owned:
            st.info("You do not own any playlists yet.")
            return
        labels = {
            f"{item.name} ({item.track_count} tracks, {item.id})": item.id for item in owned
        }
        chosen_label = st.selectbox("Your playlists", list(labels))
        playlist_id = labels[chosen_label]
        action = st.selectbox(
            "Action",
            [
                "Append matched tracks",
                "Replace playlist with matched tracks",
                "Remove matched tracks",
                "Update name / description / visibility",
            ],
        )
        mode = {
            "Append matched tracks": "append",
            "Replace playlist with matched tracks": "replace",
            "Remove matched tracks": "remove",
            "Update name / description / visibility": "update",
        }[action]

    if st.button("Apply", type="primary"):
        source = None
        if mode != "update":
            if url.strip() and description.strip():
                st.info("Both fields are filled; the YouTube URL takes precedence.")
            try:
                source = load_source(
                    url=url.strip() or None,
                    text=description if not url.strip() else None,
                )
            except RuntimeError as exc:
                show_error(str(exc))
                return
            suggested = suggest_playlist_name(
                video_title=source.video_title,
                queries=[],
            )
            if not name.strip() and mode == "create":
                st.caption(f"Suggested playlist name: {suggested}")
        progress = st.progress(0.0)
        status_box = st.empty()

        def on_progress(index: int, total: int, query: str, note: str) -> None:
            fraction = index / total if total else 1.0
            progress.progress(min(fraction, 1.0))
            label = f"Searching {index}/{total}: {query}"
            if note:
                label += f" — {note}"
            status_box.caption(label)

        try:
            _, report = run_pipeline(
                source,
                name=name.strip() or None,
                min_score=min_score,
                dry_run=dry_run,
                public=public,
                description=playlist_description.strip() or None,
                mode=mode,
                playlist_id=playlist_id,
                client=client,
                on_progress=on_progress,
            )
        except SpotifyApiError as exc:
            show_error(str(exc), exc.details)
            return
        except RuntimeError as exc:
            show_error(str(exc))
            return
        progress.progress(1.0)
        status_box.caption("Done.")
        report_tables(report)


if __name__ == "__main__":
    main()
