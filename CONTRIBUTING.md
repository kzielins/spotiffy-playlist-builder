# Contributing

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in optional Spotify Client ID / redirect overrides only if you fork the app; see [docs/spotify-app-and-tokens.md](docs/spotify-app-and-tokens.md). End users sign in with Spotify and do not need a Client Secret.

## Tests

```bash
pytest
```

OAuth helpers cover both local Streamlit (`http://127.0.0.1:8501/`) and the Cloud app (`https://spotifyplaylist.streamlit.app/`).

Merges to `main` are picked up by [Streamlit Community Cloud](https://spotifyplaylist.streamlit.app/). See [docs/streamlit-cloud.md](docs/streamlit-cloud.md). Do not put a localhost `SPOTIFY_WEB_REDIRECT_URI` in Cloud secrets.

## Changes

- Keep user-facing text in English.
- Prefer small pull requests.
- Do not commit `.env`, `.cache*`, or credential files.
- Update [CHANGELOG.md](CHANGELOG.md) under **Unreleased** when behavior changes.

## Pull requests

Fork the repository, push a branch, and open a PR against `main`.
