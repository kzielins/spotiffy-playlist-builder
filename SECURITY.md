# Security

Do **not** commit OAuth caches, Client Secrets, or GitHub personal access tokens.

- This project uses PKCE. End users never receive a Client Secret.
- CLI tokens live in `.cache-spotiffy` (gitignored). Website tokens stay in the Streamlit session, not on disk.
- Optional `.env` may override the public Client ID and redirect URIs only. See `.env.example`.
- Never paste access tokens or refresh tokens into issues, pull requests, or chat logs.

If you discover a vulnerability, open a **private** GitHub security advisory on
[kzielins/spotiffy-playlist-builder](https://github.com/kzielins/spotiffy-playlist-builder)
or contact the maintainer via GitHub. Do not file a public issue that includes secrets.
