# OAuth login

Spotiffy uses **Authorization Code with PKCE** (`SpotifyPKCE`). There is no Client Secret. The first CLI or Streamlit run sends you to Spotify so you can allow playlist search, create, and edit on **your** account.

## What happens

1. The app uses the project's public Client ID (or `SPOTIFY_CLIENT_ID` if you override it).
2. Your browser opens the Spotify consent screen with scopes `playlist-modify-public playlist-modify-private`.
3. After you accept, Spotify redirects:
   - CLI → `http://127.0.0.1:8888/callback`
   - Streamlit → `http://127.0.0.1:8501/` (query string includes `?code=` and `state`)
4. The app exchanges the code plus a PKCE verifier for an access token and a refresh token.
   - CLI stores them in `.cache-spotiffy` (gitignored).
   - Streamlit stores them only in **that browser session**, so two users on the same server cannot share a login.

Later CLI runs reuse the cache until you revoke access or delete the file. Streamlit asks again in a new session.

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

- **Redirect URI mismatch** — every URI in the Dashboard must match `.env` / the defaults exactly, including `http://127.0.0.1:8888/callback` and `http://127.0.0.1:8501/`.
- **OAuth state mismatch** — start sign-in again from the same Streamlit session; do not mix two tabs from different logins.
- **PKCE verifier missing** — Streamlit must generate the consent link and receive the redirect in the same browser session.
- **Browser does not open (CLI)** — run the CLI in a real terminal so Spotipy can start the local callback server on port 8888.

## 403 Forbidden

1. **Allowlist.** Add the user's Spotify e-mail in User Management (max 5 in Development Mode).
2. **Missing scopes.** `python main.py --relogin --check-auth`.
3. **Wrong playlist endpoint (fixed).** Writes go to `POST /v1/me/playlists` and the user's own playlist ids, never another account.
4. **Foreign playlist.** You can only edit playlists you own.

Failed calls log HTTP status, API code, `reason`, and message. Streamlit shows the same dump under *Spotify error details*.

## Signing in from Streamlit

Click **Sign in with Spotify**. After you approve access, Spotify sends you back to the app with `?code=`; login finishes automatically. Use **Log out** in the sidebar to drop the session token.

## Sign out (CLI)

```bash
python main.py --relogin
# or
rm -f .cache-spotiffy
```

You can also revoke the app under [Spotify account apps](https://www.spotify.com/account/apps/).
