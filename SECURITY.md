# Security

Do **not** commit Spotify Client secrets, OAuth caches, or GitHub personal access tokens.

- Keep credentials in a local `.env` file (see `.env.example`).
- Spotipy writes a local cache file (`.cache-spotiffy`). It is gitignored.
- Never paste tokens into issues, pull requests, or chat logs.

If you discover a vulnerability, open a **private** GitHub security advisory on
[kzielins/spotiffy-playlist-builder](https://github.com/kzielins/spotiffy-playlist-builder)
or contact the maintainer via GitHub. Do not file a public issue that includes secrets.
