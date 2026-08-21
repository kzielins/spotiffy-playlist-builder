# Streamlit Community Cloud

The public UI is deployed at **[https://spotifyplaylist.streamlit.app/](https://spotifyplaylist.streamlit.app/)**.

That origin is the Spotify OAuth `redirect_uri` for the website. It must be listed **exactly** (including the trailing slash) in the Spotify Developer Dashboard. See [oauth-login.md](oauth-login.md) and [spotify-app-and-tokens.md](spotify-app-and-tokens.md).

## App settings

In [share.streamlit.io](https://share.streamlit.io):

| Field | Value |
| --- | --- |
| Repository | `kzielins/spotiffy-playlist-builder` |
| Branch | `main` |
| Main file | `app.py` |
| URL | `https://spotifyplaylist.streamlit.app/` |

Cloud installs Python dependencies from `requirements.txt` (not `pyproject.toml`). After a merge to `main`, Streamlit pulls GitHub and restarts the app.

## Secrets

Do **not** set `SPOTIFY_WEB_REDIRECT_URI` to `http://127.0.0.1:8501/` in Cloud secrets. The app reads the live browser origin (`st.context.url`) and would otherwise send localhost to Spotify (`redirect_uri: Not matching configuration`).

Leave `SPOTIFY_CLIENT_SECRET` unset. PKCE does not use it. Optional: `SPOTIFY_CLIENT_ID` only if you fork onto another Spotify app.

## Sign in on the live site

1. Open [https://spotifyplaylist.streamlit.app/](https://spotifyplaylist.streamlit.app/).
2. Click **Sign in with Spotify**. The consent caption should show `OAuth redirect URI: https://spotifyplaylist.streamlit.app/`.
3. Approve playlist scopes (`playlist-modify-public`, `playlist-modify-private`, `playlist-read-private`).
4. Spotify sends you back to the same URL with `?code=` and `state`. Login finishes automatically.

The Sign in link is single-use. A Cloud **reboot** or a full page refresh (F5) starts a new Streamlit session: sign in again. Pending PKCE handshakes live in process memory and do not survive a reboot.

Your Spotify account must be on the Development Mode allowlist (max 5 users). Search and playlist writes from this site share the same API quota as the CLI. See [spotify-rate-limits.md](spotify-rate-limits.md).

## Local vs Cloud

| | Local | Cloud |
| --- | --- | --- |
| Command | `streamlit run app.py` | none (browser only) |
| Redirect URI | `http://127.0.0.1:8501/` | `https://spotifyplaylist.streamlit.app/` |
| Token store | this browser session | this browser session |
| Who can use it | anyone on that machine | allowlisted Spotify accounts |

Both redirect URIs must stay on the Spotify app. Deploying a fork needs its own Cloud URL added to the Dashboard.
