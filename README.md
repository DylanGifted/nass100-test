# OANDA Timed Bot

This repository contains a small Flask-based bot that places timed trades via the OANDA API and notifies via Telegram.

Quick actions I added for deployment:
- `render.yaml` — service config for Render (start command: `gunicorn main:app`).
- `requirements.txt` — Python dependencies.
- `.env.example` — example environment variables (do NOT commit real secrets).

Required environment variables
- `OANDA_API_KEY` — your OANDA API token
- `OANDA_ACCOUNT_ID` — your OANDA account id
- `OANDA_ENV` — `practice` or `live` (defaults to `practice`)
- `TELEGRAM_TOKEN` — bot token for Telegram
- `CHAT_ID` — Telegram chat id to receive notifications

Optional bot settings (can also be set in environment): `SYMBOL`, `POSITION_SIZE`, `FVG_BUFFER`, `ENTRY_START`, `ENTRY_END`, `EXIT_TIME`.

Local run

1. Copy `.env.example` to `.env` and fill values (for local dev only):

```bash
cp .env.example .env
# edit .env
```

2. Install dependencies in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Run the app locally:

```bash
export $(cat .env | xargs)
gunicorn main:app
```

Deploying to Render

1. Push repository to GitHub.
2. Create a new Web Service on Render, connect the GitHub repo.
3. Set the build command to: `pip install -r requirements.txt` (already in `render.yaml`).
4. Set the start command to: `gunicorn main:app` (already in `render.yaml`).
5. Add environment variables in Render's dashboard (do not commit secrets to the repo).

Security note

Do not commit your `.env` or API keys to the repository. If keys were accidentally committed, ask me to help remove them from git history.
