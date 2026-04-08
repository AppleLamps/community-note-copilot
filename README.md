# Community Note Copilot

Community Note Copilot is a Python Telegram bot that turns a tweet URL or pasted claim text into a draft X Community Note. It uses xAI's Responses API with server-side `web_search` and `x_search` to identify the claim, gather counter-evidence from primary sources, and produce the X Community Notes form selections plus a note draft under 280 characters.

## What It Does

- Accepts `x.com` or `twitter.com` links, or raw tweet/claim text.
- Replies with a **progress message** that is edited in place as work continues, then replaced with the final result:
  - **New analysis:** `Reading the claim...` → `Checking sources and context...` → `Drafting a community note...` (first and last steps may be skipped on fast responses).
  - **Revision** (after a saved analysis): `Reviewing the previous draft...` → `Rewriting the note with your request in mind...` → `Polishing the updated draft...`.
- Returns:
  - Quick summary line (`Quick take:` plus verdict, or `Updated draft ready` for revisions)
  - Claim and verdict
  - Recommended form selections (misleading, category, harmful)
  - Suggested Community Note text
  - Numbered sources
  - **Next prompts** (short examples of what to type for another revision)
- Commands: `/start` and `/help` show onboarding copy and examples.
- Stores per-user history in SQLite so follow-ups work when the message looks like a revision (for example `make it shorter`, `rewrite more neutrally`, `revise`, `shorten`, `trim`, and similar prefixes; see `FOLLOWUP_PREFIXES` in `bot.py`).
- Sends replies as **plain text** (no Telegram Markdown/HTML parse mode on model output), so URLs and punctuation do not trigger parse errors.
- Runs in **polling** mode locally when `TELEGRAM_WEBHOOK_URL` is unset; uses **webhooks** when that URL is set (for example on Fly.io).

## Project Layout

```text
community-note-copilot/
├── analyzer.py          # xAI Responses client, JSON parsing, citations
├── bot.py               # Telegram handlers, progress updates, revision routing
├── config.py            # Settings from environment
├── formatter.py         # User-facing message text
├── storage.py           # SQLite persistence
├── requirements.txt
├── pytest.ini
├── Dockerfile
├── .dockerignore
├── fly.toml             # Fly.io app config (see Fly section below)
├── .env.example
├── README.md
├── docs/plans/          # Design notes (optional reading)
└── tests/
```

## Requirements

- **Python 3.12+** (matches the `Dockerfile` image).

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

On macOS/Linux, activate with `source .venv/bin/activate`.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | BotFather token. |
| `XAI_API_KEY` | Yes | xAI API key. |
| `XAI_MODEL` | No | Default `grok-4.20-0309-reasoning`. |
| `XAI_BASE_URL` | No | Default `https://api.x.ai/v1`. |
| `SQLITE_PATH` | No | SQLite file path; default `community_note_copilot.sqlite3` in the working directory. |
| `TELEGRAM_WEBHOOK_URL` | No | Public HTTPS URL for Telegram webhooks. Unset = polling. |
| `TELEGRAM_WEBHOOK_SECRET` | No | Optional Telegram `secret_token` for webhook requests. |
| `TELEGRAM_LISTEN_HOST` | No | Default `0.0.0.0`. |
| `TELEGRAM_LISTEN_PORT` | No | Default `8080`. |

## Running the Bot

### Local polling

If `TELEGRAM_WEBHOOK_URL` is unset or empty, the bot uses polling:

```bash
python bot.py
```

### Webhook mode

Set `TELEGRAM_WEBHOOK_URL` to your public HTTPS endpoint (path should match how Telegram POSTs to your app), then run:

```bash
python bot.py
```

The process listens on `TELEGRAM_LISTEN_HOST`:`TELEGRAM_LISTEN_PORT` and registers the webhook with Telegram.

## Example Interaction

User:

```text
https://x.com/example/status/1234567890
```

Bot (same message edited in place; first line shown):

```text
Reading the claim...
```

The same message is edited through the remaining progress lines, then replaced with structured output: **Quick take**, **Claim**, **Verdict**, **Recommended form selections**, **Suggested Community Note**, **Sources**, and **Next prompts**.

Follow-up (only if the bot already stored an analysis for this user and the text matches a revision prefix):

```text
make it shorter
```

The bot loads the latest analysis from SQLite and asks xAI for a revised draft.

## Deployment Notes

For a VPS, webhook mode avoids a long-lived polling process in one shell.

Suggested setup:

1. Run the bot in a virtual environment under a process manager (for example `systemd`).
2. Terminate TLS with Nginx or Caddy in front of the app.
3. Proxy the public HTTPS URL you set in `TELEGRAM_WEBHOOK_URL` to `TELEGRAM_LISTEN_PORT`.
4. Keep `.env` off publicly served paths; put the SQLite file on persistent disk if you care about history across restarts.
5. Back up the SQLite file if you want follow-up history after migrations.

Example `systemd` `ExecStart`:

```bash
/path/to/venv/bin/python /srv/community-note-copilot/bot.py
```

## Fly.io Deployment

This repo includes `Dockerfile`, `.dockerignore`, and `fly.toml`.

- Public HTTP is routed to `internal_port` **8080**; the bot listens on `0.0.0.0:8080` by default.
- The checked-in `fly.toml` sets `primary_region = "ams"`, `auto_stop_machines = "stop"`, and `min_machines_running = 0`. That can **cold-start** on traffic; for snappier webhooks, consider `min_machines_running = 1` (and weigh cost).
- **SQLite persistence:** the template `fly.toml` does **not** define a volume mount. Without one, the database lives on ephemeral machine disk. For production history, create a Fly volume, add a `[[mounts]]` section pointing at `/data`, and set `SQLITE_PATH=/data/community_note_copilot.sqlite3` (secret or `[env]`). Create the volume in the **same region** as `primary_region` (for example `ams`).

Example flow after `fly launch`:

```bash
cd community-note-copilot
fly launch --no-deploy
fly secrets set TELEGRAM_BOT_TOKEN=... XAI_API_KEY=... TELEGRAM_WEBHOOK_URL=https://<your-app>.fly.dev
fly volumes create data --region ams --size 1
# Add [[mounts]] source=data destination=/data to fly.toml, then:
fly secrets set SQLITE_PATH=/data/community_note_copilot.sqlite3
fly deploy
```

After deploy:

1. Check health with `fly checks list` (if configured) and `fly status`.
2. Send `/start` in Telegram and confirm the bot responds.
3. Use `fly logs` if updates are missing.

**Scaling:** use a **single** machine for plain SQLite unless you adopt replicated storage (for example LiteFS) or move history to Postgres.

## Development

Run tests:

```bash
python -m pytest tests -v
```

`pytest.ini` is picked up automatically from the repo root.
