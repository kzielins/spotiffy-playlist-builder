# Spotiffy playlist builder

Turn a **YouTube video description** or any **pasted text** into a **Spotify playlist**.

Each line is cleaned (timestamps, numbering, URLs) and searched on Spotify. The best matching track is kept when the score is high enough. Lines that look like “subscribe” noise are skipped. The playlist name is optional: if you omit it, the tool suggests one from the video title or the first useful line.

## Features

- CLI and a simple Streamlit UI
- YouTube descriptions via `yt-dlp` (metadata only, no video download)
- Mixed text: not only `Artist - Title` lines
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
cp .env.example .env
```

Edit `.env` with your Spotify Client ID, Client Secret, and redirect URI
`http://127.0.0.1:8888/callback`. Details: [docs/spotify-app-and-tokens.md](docs/spotify-app-and-tokens.md).

## CLI

```bash
python main.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
python main.py --url "https://www.youtube.com/watch?v=VIDEO_ID" --name "Summer Mix"
python main.py --text "00:00 Artist - Title
Thanks for watching
Blinding Lights"
python main.py --file tracks.txt --dry-run
python main.py --stdin
```

`--name` is optional. `--dry-run` prints matches without creating a playlist.
The first Spotify login opens a browser; see [docs/oauth-login.md](docs/oauth-login.md).

## Streamlit

```bash
streamlit run app.py
```

Paste a YouTube URL **or** a description. If both are filled, the URL wins.
Leave the playlist name empty to use a suggestion. Click **Create playlist**.

## License

[MIT](LICENSE)
