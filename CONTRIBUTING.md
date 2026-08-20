# Contributing

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in Spotify credentials as described in [docs/spotify-app-and-tokens.md](docs/spotify-app-and-tokens.md).

## Changes

- Keep user-facing text in English.
- Prefer small pull requests.
- Do not commit `.env`, `.cache*`, or credential files.
- Update [CHANGELOG.md](CHANGELOG.md) under **Unreleased** when behavior changes.

## Pull requests

Fork the repository, push a branch, and open a PR against `main`.
