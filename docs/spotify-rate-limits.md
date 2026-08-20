# Spotify rate limits and quota

The Web API has two separate brakes. Both return HTTP **429**. This project uses one shared Client ID, so **every user of the Streamlit app and CLI counts against the same pool**.

## Rate limit vs quota

| Signal | Meaning | What to do |
| --- | --- | --- |
| 429 and `Retry-After` of a few seconds | Rolling **30-second** rate limit | The app waits up to 15 seconds, shows progress, then retries once |
| 429 with `reason: QUOTA_EXCEEDED` or `Retry-After` of hours | **Development Mode quota** for the app | The app **stops**. Wait until that window ends. Do not retry in a loop |

Spotify does not publish exact numeric limits. They differ for Development Mode vs Extended Quota Mode. Official docs: [rate limits](https://developer.spotify.com/documentation/web-api/concepts/rate-limits) and [quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes).

## How this app stays under the limit

- At most **two** Spotify searches per description line, and it stops early when the match is already strong.
- About **120 ms** between searches so a long mix does not empty the 30-second window at once.
- Spotipy **retries are disabled**. A 22-hour `Retry-After` is never slept through.
- Listing playlists is cached in the Streamlit session; use **Refresh playlist list** only when you need a new fetch.

You can still exhaust Development Mode quota by running many mixes, many browser tabs, or CLI and Streamlit at the same time.

## After a quota error

Wait for the time shown in the error (often until the next day). Then run a **short** dry-run, not a 50-track mix. Avoid extra **Edit existing playlist** refreshes.

## Optional: request a larger pool (Extended Quota Mode)

Extended Quota Mode removes the 5-user allowlist and raises rate limits. 429 backoff still applies.

1. Open the app in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. **Settings** → **Quota extension Request** (four steps) → **Submit**.
3. Review can take up to six weeks. Status shows as **Sent**.

**As of 15 May 2025**, Spotify only accepts these requests from **organisations** (company email, legally registered business, launched service, on the order of **250k MAU**, key Spotify markets, Developer Policy). A personal hobby app on Streamlit Community Cloud **is unlikely to qualify**. There is no in-app workaround for that policy.

Partner intake: [Quota extension for new potential partners](https://developer.spotify.com/documentation/web-api/concepts/quota-modes).
