# Tutorial

This walkthrough converts a YouTube description (or any pasted list) into a Spotify playlist, or edits one you already own.

## 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

A `.env` file is optional. End users do not need a Client Secret. See [spotify-app-and-tokens.md](spotify-app-and-tokens.md) if you fork the project or change redirect URIs.

Ask the project owner to add your Spotify account e-mail under Dashboard → User Management (Development Mode, max 5 people).

## 2. First login (CLI)

```bash
python main.py --text "The Weeknd - Blinding Lights" --dry-run
```

A browser opens for Spotify consent. Confirm the account and scopes:

```bash
python main.py --check-auth
python main.py --list-playlists
```

See [oauth-login.md](oauth-login.md) if the redirect URI does not match, if scopes are missing, or if a write returns 403.

## 3. YouTube URL → new playlist

```bash
python main.py --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

`yt-dlp` reads the description only (no video file). The playlist name defaults to the video title.

## 4. Pasted mixed text

```bash
python main.py --text "00:00 Artist One - First Track
Subscribe for more
Blinding Lights"
```

Weak matches are skipped. Tune with `--min-score` (default `0.45`). Playlists are private unless you pass `--public`.

## 5. Edit an existing playlist

```bash
python main.py --list-playlists
python main.py --mode append --playlist-id PLAYLIST_ID --text "Daft Punk - One More Time"
python main.py --mode replace --playlist-id PLAYLIST_ID --file tracks.txt
python main.py --mode remove --playlist-id PLAYLIST_ID --text "Blinding Lights"
python main.py --mode update --playlist-id PLAYLIST_ID --name "New title" --private
```

You can only change playlists you own.

## 6. Streamlit UI

```bash
streamlit run app.py
```

Sign in with Spotify (automatic redirect back to this page). On [Streamlit Cloud](https://spotifyplaylist.streamlit.app) the consent URL uses `https://spotifyplaylist.streamlit.app/` — that URI must be in the Spotify Dashboard. Use **Create new playlist** or pick one of yours and append, replace, remove, or update details.
