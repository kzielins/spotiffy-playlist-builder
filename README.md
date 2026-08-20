# Spotiffy playlist builder

Turn a **YouTube video description** or any **pasted text** into a **Spotify playlist**, or edit a playlist you already own.

Each line is cleaned (timestamps, numbering, URLs) and searched on Spotify. The best matching track is kept when the score is high enough. Lines that look like “subscribe” noise are skipped. The playlist name is optional: if you omit it, the tool suggests one from the video title or the first useful line.

Users sign in with Spotify in the browser. **No Client Secret and no hand-made token** are required.

## Features

- CLI and a Streamlit UI
- OAuth PKCE (one shared Client ID; per-session tokens on the website)
- YouTube descriptions via `yt-dlp` (metadata only, no video download)
- Mixed text: not only `Artist - Title` lines
- Create, append, replace, remove, and rename/visibility updates on **your** playlists
- Fallback Spotify search and a match-score threshold
- Batch add (100 URIs) and a found vs skipped report

## Documentation

- [Tutorial](docs/tutorial.md)
- [Create a Spotify app and tokens](docs/spotify-app-and-tokens.md)
- [OAuth login](docs/oauth-login.md)
- [GitHub PAT (publishing only)](docs/github.md)
- [Authors](AUTHORS.md) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

## Install

Python 3.11+ is required.

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Ask the project owner to add your Spotify e-mail to the app allowlist (Development Mode, max 5 users). Details: [docs/spotify-app-and-tokens.md](docs/spotify-app-and-tokens.md).

## CLI

```bash
python main.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
python main.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --name "Summer Mix"
python main.py --text "00:00 Artist - Title
Thanks for watching
Blinding Lights"
python main.py --file tracks.txt --dry-run
python main.py --stdin
python main.py --check-auth
python main.py --list-playlists
python main.py --mode append --playlist-id PLAYLIST_ID --text "Daft Punk - One More Time"
```

`--name` is optional. `--dry-run` prints matches without writing to Spotify.
`--public` / `--private` set visibility. `--mode` is `create` (default), `append`,
`replace`, `remove`, or `update`. The first login opens a browser; see
[docs/oauth-login.md](docs/oauth-login.md).

## Streamlit

```bash
streamlit run app.py
```

Click **Sign in with Spotify**. Paste a YouTube URL **or** a description. Create a
new playlist or pick one you own and append, replace, remove, or update its details.

## License

[MIT](LICENSE)
