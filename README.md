# Community Note Copilot

Community Note Copilot is a Python Telegram bot that turns a tweet URL or pasted claim text into a draft X Community Note. It uses xAI's Responses API with server-side `web_search` and `x_search` to identify the claim, gather counter-evidence from primary sources, and produce the exact X Community Notes form selections plus a note draft under 280 characters.

## What It Does

- Accepts `x.com` or `twitter.com` links, or raw tweet/claim text.
- Replies immediately with `🔍 Analyzing…`, then edits that message with the finished output.
- Returns:
  - Claim identified
  - Verdict
  - Community Notes form selections
  - Draft note text
  - Numbered source list
- Stores per-user history in SQLite so users can send follow-ups like `make it shorter` or `rewrite this more neutrally`.
- Runs in polling mode locally and is webhook-ready for deployment.

## Project Layout

```text
community-note-copilot/
├── analyzer.py
├── bot.py
├── config.py
├── formatter.py
├── storage.py
├── requirements.txt
├── .env.example
├── README.md
└── tests/
```

## Setup

1. Create a Telegram bot with [BotFather](https://t.me/BotFather) and copy the bot token.
2. Create an xAI API key from [console.x.ai](https://console.x.ai).
3. Copy `.env.example` to `.env` and fill in `TELEGRAM_BOT_TOKEN` and `XAI_API_KEY`.
4. Install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Environment Variables

- `TELEGRAM_BOT_TOKEN`: BotFather token for your Telegram bot.
- `XAI_API_KEY`: API key from xAI console.
- `XAI_MODEL`: Defaults to `grok-4.20-0309-reasoning`.
- `XAI_BASE_URL`: Defaults to `https://api.x.ai/v1`.
- `SQLITE_PATH`: Path to the SQLite database file.
- `TELEGRAM_WEBHOOK_URL`: Public HTTPS webhook URL for Telegram delivery. Leave empty for polling mode.
- `TELEGRAM_WEBHOOK_SECRET`: Optional secret token used to protect webhook requests.
- `TELEGRAM_LISTEN_HOST`: Host interface for webhook listener.
- `TELEGRAM_LISTEN_PORT`: Port for webhook listener.

## Running the Bot

### Local Polling

If `TELEGRAM_WEBHOOK_URL` is unset, the bot starts in polling mode:

```bash
python bot.py
```

### Webhook Mode

Set `TELEGRAM_WEBHOOK_URL` to your public HTTPS endpoint, then run:

```bash
python bot.py
```

The bot will start a webhook listener on `TELEGRAM_LISTEN_HOST:TELEGRAM_LISTEN_PORT` and register the webhook URL with Telegram.

## Example Interaction

User:

```text
https://x.com/example/status/1234567890
```

Bot:

```text
🔍 Analyzing…
```

Then the bot edits the placeholder into a message with:

- Claim identified
- Verdict
- CN Form Selections
- Draft Note Text
- Sources

Follow-up example:

```text
make it shorter
```

The bot uses the user's most recent saved analysis from SQLite and asks xAI for a revised note draft.

## Deployment Notes

For a VPS, webhook mode is the better default because Telegram pushes updates directly to the bot and you avoid a long-polling process tied to one shell session.

Recommended VPS setup:

1. Run the bot inside a virtual environment under a process manager such as `systemd`.
2. Put Nginx or Caddy in front of the bot and terminate TLS there.
3. Proxy the public HTTPS webhook path to `TELEGRAM_LISTEN_PORT`.
4. Store `.env` outside public directories and keep the SQLite file on persistent disk.
5. Back up the SQLite file if you want to preserve user follow-up history after server migration.

Example `systemd` service command:

```bash
/path/to/venv/bin/python /srv/community-note-copilot/bot.py
```

## Fly.io Deployment

This repo now includes `Dockerfile`, `.dockerignore`, and `fly.toml` for Fly.io.

Why this setup:

- Fly routes public traffic to the port declared in `internal_port`, so the bot is configured to listen on `0.0.0.0:8080`.
- SQLite needs persistent disk, so the Fly config mounts a volume at `/data` and stores the database at `/data/community_note_copilot.sqlite3`.
- This bot should run as a single instance when using plain SQLite. Do not scale it horizontally unless you switch to a replicated SQLite strategy such as LiteFS or move history storage to Postgres.

Recommended deploy steps:

```bash
cd community-note-copilot
fly launch --no-deploy
fly secrets set TELEGRAM_BOT_TOKEN=... XAI_API_KEY=... TELEGRAM_WEBHOOK_URL=https://<your-app>.fly.dev
fly volumes create data --region iad --size 1
fly deploy
```

After deploy:

1. Confirm the app is healthy with `fly checks list`.
2. Confirm the webhook endpoint is registered by sending `/start` to the bot in Telegram.
3. Inspect logs with `fly logs` if Telegram does not deliver updates.

Operational notes:

- Keep `min_machines_running = 1` because a stopped Machine can delay webhook delivery.
- The included Fly config uses a TCP health check instead of an HTTP health check, because the PTB webhook server does not expose a dedicated unauthenticated health endpoint.
- If you want a stable custom hostname, point `TELEGRAM_WEBHOOK_URL` at that HTTPS domain and redeploy or update secrets.

## Development

Run tests:

```bash
python -m pytest tests -c pytest.ini -v
```
