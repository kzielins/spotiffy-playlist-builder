# OAuth login

Spotiffy uses **Authorization Code with PKCE** (`SpotifyPKCE`). There is no Client Secret. The first CLI or Streamlit run sends you to Spotify so you can allow playlist search, create, and edit on **your** account.

## What happens

1. The app uses the project's public Client ID (or `SPOTIFY_CLIENT_ID` if you override it).
2. Your browser opens the Spotify consent screen with scopes `playlist-modify-public playlist-modify-private`.
3. After you accept, Spotify redirects:
   - CLI → `http://127.0.0.1:8888/callback`
   - Local Streamlit → `http://127.0.0.1:8501/`
   - Streamlit Cloud → the live app origin, for example `https://spotifyplaylist.streamlit.app/`
   Query string includes `?code=` and `state`. The Sign-in page shows the exact redirect URI being sent.
4. The app exchanges the code plus a PKCE verifier for an access token and a refresh token.
   - CLI stores them in `.cache-spotiffy` (gitignored).
   - Streamlit stores them only in **that browser session**, so two users on the same server cannot share a login. Refreshing the page (F5) starts a new session and you must sign in again.

Later CLI runs reuse the cache until you revoke access or delete the file. Streamlit asks again in a new session.

The Streamlit **Sign in with Spotify** link is **single-use** and expires after a few minutes. Do not bookmark it. If you see that the link expired or was already used, click Sign in again on the app page.

## Who is who in this flow

- **Client ID** identifies this project. It is public. Users do not register their own Spotify developer app.
- **Your Spotify account** grants playlist rights on the consent screen.
- Playlists are always created or edited on the account that approved consent. A listener account is enough; Premium is required only for the **app owner** in Development Mode.

## Development Mode limit

Spotify currently allows **at most 5 allowlisted users** per Development Mode app. The owner must add each person's Spotify e-mail under Dashboard → User Management. Anyone else can often complete the consent screen, then get **403** on search or playlist writes. There is no code workaround; the owner must add the user or apply for Extended Quota Mode.

## Check the connection

```bash
python main.py --check-auth
python main.py --list-playlists
```

`--check-auth` prints the signed-in user, granted scopes, redirect URI, and cache path — never the token. Expected scopes:

```
playlist-modify-private playlist-modify-public
```

## Common errors

- **Redirect URI mismatch / `Not matching configuration`** — Spotify compares the `redirect_uri` query parameter to the Dashboard list **exactly** (scheme, host, port, path, trailing slash). Local Streamlit uses `http://127.0.0.1:8501/`; [spotifyplaylist.streamlit.app](https://spotifyplaylist.streamlit.app) uses `https://spotifyplaylist.streamlit.app/`. Both must be listed. CLI stays `http://127.0.0.1:8888/callback`. Do not set `SPOTIFY_WEB_REDIRECT_URI` to localhost in Streamlit Cloud secrets.
- **Sign-in link expired or was already used** — Streamlit cannot keep OAuth `state` across Spotify's redirect in `session_state`. The handshake lives in process memory for a few minutes and is consumed once. Click **Sign in with Spotify** again; do not reuse an old tab or bookmark.
- **PKCE verifier missing** — start sign-in from the app so a fresh consent URL is generated; do not paste an old authorize URL.
- **Browser does not open (CLI)** — run the CLI in a real terminal so Spotipy can start the local callback server on port 8888.

## 403 Forbidden

1. **Allowlist.** Add the user's Spotify e-mail in User Management (max 5 in Development Mode).
2. **Missing scopes.** `python main.py --relogin --check-auth`.
3. **Wrong playlist endpoint (fixed).** Writes go to `POST /v1/me/playlists` and the user's own playlist ids, never another account.
4. **Foreign playlist.** You can only edit playlists you own.

Failed calls log HTTP status, API code, `reason`, and message. Streamlit shows the same dump under *Spotify error details*.

## Signing in from Streamlit

Click **Sign in with Spotify**. After you approve access, Spotify sends you back to the app with `?code=`; login finishes automatically. The link is single-use and short-lived. After a page refresh you must sign in again because the token lives only in the browser session. Use **Log out** in the sidebar to drop it.

## Sign out (CLI)

```bash
python main.py --relogin
# or
rm -f .cache-spotiffy
```

You can also revoke the app under [Spotify account apps](https://www.spotify.com/account/apps/).
