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

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    st.set_page_config(page_title="Spotiffy playlist builder", layout="centered")
    st.title("YouTube description → Spotify playlist")
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

    if st.button("Create playlist", type="primary"):
        if url.strip() and description.strip():
            st.info("Both fields are filled; the YouTube URL takes precedence.")
        try:
            source = load_source(
                url=url.strip() or None,
                text=description if not url.strip() else None,
            )
        except RuntimeError as exc:
            st.error(str(exc))
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
                )
            except RuntimeError as exc:
                st.error(str(exc))
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
                use_container_width=True,
            )
        else:
            st.write("No confident matches.")
        st.subheader("Skipped")
        if report.skipped:
            st.dataframe(
                [{"line": s.query, "reason": s.reason} for s in report.skipped],
                use_container_width=True,
            )
        else:
            st.write("Nothing skipped.")


if __name__ == "__main__":
    main()
