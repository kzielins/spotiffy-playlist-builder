# OAuth login

Spotipy uses **Authorization Code** flow (`SpotifyOAuth`). The first CLI or Streamlit run opens a browser so you can allow the app to create playlists on your account.

## What happens

1. The app reads Client ID / Secret from `.env`.
2. Your browser opens the Spotify consent screen.
3. After you accept, Spotify redirects to `http://127.0.0.1:8888/callback`.
4. Spotipy stores a refreshable token in `.cache-spotiffy` (gitignored).

Later runs reuse the cache until you revoke access or delete the file.

## Common errors

- **Redirect URI mismatch** — the URI in the Dashboard must match `.env` exactly, including `http://127.0.0.1:8888/callback`.
- **INVALID_CLIENT** — wrong Client ID or Secret.
- **Browser does not open** — run the CLI in a real terminal (not a headless CI job) so Spotipy can start a local callback server.

## Sign out

Delete the cache file in the project root:

```bash
rm -f .cache-spotiffy .cache*
```

The next command will prompt for login again. You can also revoke the app under [Spotify account apps](https://www.spotify.com/account/apps/).
