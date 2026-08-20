# OAuth login

Spotipy uses **Authorization Code** flow (`SpotifyOAuth`). The first CLI or Streamlit run opens a browser so you can allow the app to create playlists on your account.

## What happens

1. The app reads Client ID / Secret from `.env`.
2. Your browser opens the Spotify consent screen.
3. After you accept, Spotify redirects to `http://127.0.0.1:8888/callback`.
4. Spotipy stores a refreshable token in `.cache-spotiffy` (gitignored).

Later runs reuse the cache until you revoke access or delete the file.

## Who is who in this flow

- **Client ID / Secret** identify the *app* and stay in `.env`.
- **Your Spotify account** grants the app permission during the browser consent step.
- The playlist is always created on the account that approved the consent screen, so an ordinary (non-Premium) account is enough.

## Check the connection

```bash
python main.py --check-auth
```

It prints the signed-in user, the granted scopes, the redirect URI, and the cache file — never the token itself. Expected scopes:

```
playlist-modify-private playlist-modify-public
```

## Common errors

- **Redirect URI mismatch** — the URI in the Dashboard must match `.env` exactly, including `http://127.0.0.1:8888/callback`.
- **INVALID_CLIENT** — wrong Client ID or Secret.
- **Browser does not open** — run the CLI in a real terminal, or use the Streamlit sign-in flow below, which never needs a browser on the server.

## 403 Forbidden when creating a playlist

Search works, then the playlist call fails. Work through these in order:

1. **Wrong endpoint (fixed in this project).** Creating playlists through `POST /v1/users/{user_id}/playlists` can return 403 even with valid scopes. Spotiffy now calls `POST /v1/me/playlists`, which always targets the account that approved consent. If you forked an older revision, apply the same change.
2. **Missing scopes.** Run `python main.py --check-auth`. If `MISSING scopes` is listed, the cached token predates a scope change:

```bash
python main.py --relogin --check-auth
```

3. **App in Development mode.** In the Spotify Dashboard, open your app → *User Management* and add the e-mail of every account that should use it. Accounts outside that list get 403 on write calls.
4. **Stale or foreign token.** Delete the cache and consent again with the intended account:

```bash
rm -f .cache-spotiffy && python main.py --check-auth
```

Every failed call is logged with the full server response — HTTP status, Spotify error code, `reason`, and message — so the log tells you which of the cases above you hit. In Streamlit the same dump is available under *Spotify error details*.

## Signing in from Streamlit

The Streamlit app never opens a browser on the server. When no token is cached it shows a consent link; approve access, then copy the whole URL you were redirected to (it contains `?code=`) and paste it into **Redirect URL** → *Finish sign-in*. The sidebar has **Check connection** and **Re-authenticate** (clears the cached token).

## Sign out

Delete the cache file in the project root:

```bash
rm -f .cache-spotiffy .cache*
```

The next command will prompt for login again. You can also revoke the app under [Spotify account apps](https://www.spotify.com/account/apps/).
