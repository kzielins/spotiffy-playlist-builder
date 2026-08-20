# Tutorial

This walkthrough converts a YouTube description (or any pasted list) into a Spotify playlist.

## 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2. Spotify app

Follow [spotify-app-and-tokens.md](spotify-app-and-tokens.md) so `.env` has:

- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback`

## 3. First login

Run a dry search. Spotipy opens a browser for consent:

```bash
python main.py --text "The Weeknd - Blinding Lights" --dry-run
```

See [oauth-login.md](oauth-login.md) if the redirect URI does not match.

## 4. YouTube URL

```bash
python main.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

`yt-dlp` reads the description only (no video file). The playlist name defaults to the video title.

## 5. Pasted mixed text

You can paste timestamps, promo lines, and titles together:

```text
00:00 Artist One - First Track
Subscribe for more
Blinding Lights
01:12 Second Artist – Another Song
```

```bash
python main.py --text "paste the block here"
```

Weak Spotify matches are skipped. Tune with `--min-score` (default `0.45`).

## 6. Streamlit UI

```bash
streamlit run app.py
```

Use the URL field **or** the large text box, optionally set a playlist name, then **Create playlist**.
