# GitHub personal access token

You do **not** need a GitHub token to convert descriptions to Spotify playlists. A token is only for publishing this repository with the GitHub CLI (`gh`).

## Create a classic PAT

1. GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**.
2. Generate a token with `repo` scope for public repositories.
3. Store it outside the git tree (for example `~/.ssh/github-token`). Never commit it.

## Authenticate the GitHub CLI

```bash
gh auth login --hostname github.com --with-token < token-file-first-line
gh auth status
```

Classic tokens start with `ghp_`.

## Push this project

```bash
git init -b main
git add .
git commit -m "chore: initial import"
gh repo create kzielins/spotiffy-playlist-builder --public --source=. --remote=origin --push
```

Confirm `.env` and `.cache*` are ignored before the first commit.
