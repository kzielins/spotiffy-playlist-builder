# Spotify app and tokens

The converter uses the [Spotify Web API](https://developer.spotify.com/documentation/web-api) through **Authorization Code with PKCE**. People who use the CLI or the website **do not need a Client Secret** and do not generate tokens by hand. They sign in with Spotify in the browser.

The **project owner** registers one Spotify app. Its public Client ID is built into this repository (override with `SPOTIFY_CLIENT_ID` if you fork).

## End users

1. Open the Streamlit app or run the CLI.
2. Approve **playlist-modify-public** and **playlist-modify-private** on the Spotify consent page.
3. After redirect, the app stores a user access token (CLI: `.cache-spotiffy`; Streamlit: that browser session only).

You never paste a Client Secret. Search, playlist create, and playlist edit all use the token Spotify issues after that consent.

## Project owner (once)

1. Sign in at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard). The owner account must have **Spotify Premium** while the app stays in Development Mode.
2. Open the app (or **Create app** if you fork).
3. Add these redirect URIs **exactly** (trailing slashes matter):

   - `http://127.0.0.1:8888/callback` (CLI)
   - `http://127.0.0.1:8501/` (local Streamlit)
   - `https://spotifyplaylist.streamlit.app/` (Streamlit Community Cloud)

   Prefer `127.0.0.1` over `localhost`. They are not interchangeable for Spotify. If Sign in shows `redirect_uri: Not matching configuration`, the URI on the login screen is missing from this list.
4. Under **User Management**, add up to **5** Spotify account e-mails that may use the app. Development Mode will not serve anyone else until you obtain [Extended Quota Mode](https://developer.spotify.com/documentation/web-api/concepts/quota-modes).

## Optional local overrides

Copy `.env.example` to `.env` only if you fork the app or change redirect URIs:

```env
# Leave empty to use this project's public Client ID
SPOTIFY_CLIENT_ID=
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
SPOTIFY_WEB_REDIRECT_URI=http://127.0.0.1:8501/
```

Do **not** put a Client Secret in `.env`. PKCE does not use it. On Streamlit Cloud, leave `SPOTIFY_WEB_REDIRECT_URI` unset so the app uses `https://spotifyplaylist.streamlit.app/` from the browser.

## Scopes requested by this project

- `playlist-modify-public` — create and edit public playlists
- `playlist-modify-private` — create and edit private playlists

Those scopes also cover searching the catalog while a user is signed in. No other scopes are required.
