# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- OAuth Authorization Code with PKCE so end users sign in with Spotify in the browser and never need a Client Secret or a hand-made token.
- Streamlit stores tokens only in the current browser session; CLI still uses `.cache-spotiffy`.
- Playlist editor: list owned playlists, append, replace, remove matched tracks, and update name/description/visibility (`--mode`, `--playlist-id`, `--list-playlists`, Streamlit **Edit existing playlist**).

### Changed

- Replaced `SpotifyOAuth` (client secret) with `SpotifyPKCE`. `SPOTIFY_CLIENT_SECRET` is no longer used.
- Streamlit completes login from the Spotify redirect (`?code=`) instead of asking users to paste a URL.

### Fixed

- Streamlit Sign in uses the live app origin (`st.context.url`) as Spotify `redirect_uri`, so Community Cloud is not stuck on `http://127.0.0.1:8501/`.
- Playlists are created through `POST /v1/me/playlists` instead of `POST /v1/users/{id}/playlists`, which returned 403 Forbidden even with valid `playlist-modify-*` scopes.
- Suggested playlist names are collapsed to a single line and clamped to Spotify's 100-character limit.
- Promotional description lines (`Track list:`, `Stream/Download`, arrow and emoji decorations, contact handles) are filtered out before searching, instead of being rejected later by the score threshold.
- Clearing the token cache and then checking the connection no longer crashes Streamlit.

### Added (debugging)

- `--check-auth` reports the connected account, granted scopes, redirect URI, and token cache; `--relogin` clears the cached CLI token.
- `--public` / `--private` set playlist visibility (create default: private).
- Failed Spotify calls log the full server response — HTTP status, API code, `reason`, and message — and Streamlit shows the same dump under *Spotify error details*.

## [0.1.0] - 2026-08-20

### Added

- CLI (`main.py`) and Streamlit UI (`app.py`) to turn YouTube descriptions or pasted text into Spotify playlists.
- Line-by-line Spotify search with scoring and a configurable minimum score.
- Optional playlist name with an automatic suggestion from the video title or first candidate line.
- Documentation for Spotify app credentials, OAuth login, and GitHub publishing.

[Unreleased]: https://github.com/kzielins/spotiffy-playlist-builder/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kzielins/spotiffy-playlist-builder/releases/tag/v0.1.0
