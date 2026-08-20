"""Streamlit UI for Spotiffy playlist builder."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.parser import suggest_playlist_name
from src.pipeline import load_source, run_pipeline
from src.spotify_client import SpotifyApiError, SpotifyClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def show_error(message: str, details: str = "") -> None:
    st.error(message)
    if details:
        with st.expander("Spotify error details"):
            st.code(details)


def connect_spotify() -> SpotifyClient | None:
    """Return a ready client, or render the manual OAuth step and return None."""
    try:
        client = SpotifyClient(open_browser=False)
    except RuntimeError as exc:
        show_error(str(exc))
        return None
    if client.has_cached_token():
        return client

    st.warning("Spotify account not connected yet.")
    st.markdown(f"1. [Open the Spotify consent page]({client.authorize_url()})")
    st.markdown(
        "2. Approve access, then copy the full URL you land on "
        "(it contains `?code=`) and paste it below."
    )
    pasted = st.text_input("Redirect URL", key="oauth_redirect")
    if st.button("Finish sign-in"):
        try:
            client.complete_auth(pasted)
        except SpotifyApiError as exc:
            show_error(str(exc), exc.details)
            return None
        except RuntimeError as exc:
            show_error(str(exc))
            return None
        st.success("Spotify connected. Click 'Create playlist' again.")
        return client
    return None


def render_sidebar() -> None:
    with st.sidebar:
        st.subheader("Spotify account")
        if st.button("Check connection"):
            try:
                status = SpotifyClient(open_browser=False).auth_status()
            except SpotifyApiError as exc:
                show_error(str(exc), exc.details)
            except RuntimeError as exc:
                show_error(str(exc))
            else:
                if not status["connected"]:
                    st.warning("Not connected. Press 'Create playlist' to sign in.")
                else:
                    st.write(f"User: `{status['user_id']}`")
                    st.write(f"Scopes: `{' '.join(status['granted_scopes']) or '-'}`")
                    missing = status["missing_scopes"]
                    if missing:
                        st.error(f"Missing scopes: {' '.join(missing)}")
                    else:
                        st.success("Playlist scopes granted.")
        if st.button("Re-authenticate"):
            try:
                removed = SpotifyClient(open_browser=False).sign_out()
            except RuntimeError as exc:
                show_error(str(exc))
            else:
                st.info("Token cache cleared." if removed else "No cached token found.")


def main() -> None:
    st.set_page_config(page_title="Spotiffy playlist builder", layout="centered")
    st.title("YouTube description → Spotify playlist")
    render_sidebar()
    st.write(
        "Paste a YouTube URL **or** any description / mixed text. "
        "Each line is searched on Spotify; weak matches are skipped. "
        "Leave the playlist name empty to use a suggested title."
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
    min_score = st.slider("Minimum match score", 0.0, 1.0, 0.45, 0.05)
    dry_run = st.checkbox("Dry run (search only, do not create a playlist)")
    public = st.checkbox("Public playlist", value=False)

    if st.button("Create playlist", type="primary"):
        client = connect_spotify()
        if client is None:
            return
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
        chosen = name.strip() or None
        if not chosen:
            st.caption(f"Suggested playlist name: {suggested}")
        with st.spinner("Searching Spotify…"):
            try:
                _, report = run_pipeline(
                    source,
                    name=chosen,
                    min_score=min_score,
                    dry_run=dry_run,
                    public=public,
                    client=client,
                )
            except SpotifyApiError as exc:
                show_error(str(exc), exc.details)
                return
            except RuntimeError as exc:
                show_error(str(exc))
                return
        st.success(f"Playlist name: {report.playlist_name}")
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


if __name__ == "__main__":
    main()
