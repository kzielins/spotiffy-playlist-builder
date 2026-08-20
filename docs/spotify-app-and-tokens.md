# Spotify app and tokens

The converter uses the [Spotify Web API](https://developer.spotify.com/documentation/web-api) through Spotipy. You need a **Client ID** and **Client Secret** from the Developer Dashboard. Those values are *not* the same as the user access token created after browser login (see [oauth-login.md](oauth-login.md)).

## Create an app

1. Sign in at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard).
2. Click **Create app**.
3. Give it a name and description (for example `Spotiffy playlist builder`).
4. Add the redirect URI exactly:

   `http://127.0.0.1:8888/callback`

   Prefer `127.0.0.1` over `localhost`. They are not interchangeable for Spotify.
5. Save. Open the app and copy **Client ID**. Reveal and copy **Client Secret**.

## Local environment file

Copy `.env.example` to `.env` in the project root (never commit `.env`):

```env
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

## Rotate a secret

If a secret leaks, open the Dashboard app, rotate the Client Secret, update `.env`, and delete `.cache-spotiffy` so the next run requests a new user token.

## Scopes requested by this project

- `playlist-modify-public`
- `playlist-modify-private`

No other scopes are required.
