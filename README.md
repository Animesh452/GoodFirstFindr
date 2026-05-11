# GoodFirstFindr

GoodFirstFindr is a FastAPI web app that finds open GitHub issues labeled `good first issue`, filters out assigned issues and linked PRs, ranks recommendations against a hardcoded ML/backend skill profile, and explains each match with Groq.

## Features

- GitHub issue search through `GET /search`
- Four-part scoring: skill match, repo health, competition, freshness
- Filters for open, unassigned issues and excludes linked PRs where GitHub search supports it
- Groq-powered recommendation reasons with deterministic fallback text
- Daily Gmail SMTP digest scheduled with APScheduler
- Saved issues stored in SQLite per browser-generated client id
- REST endpoints: `GET /search`, `GET /saved`, `POST /save`, `DELETE /saved/{id}`

## Local Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

## Environment

Required for the full production path:

- `GITHUB_TOKEN`
- `GROQ_API_KEY`
- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`
- `RECIPIENT_EMAIL`

Optional:

- `GROQ_MODEL`, default `llama-3.3-70b-versatile`
- `DIGEST_ENABLED`, default `true`
- `DIGEST_TIME`, default `08:00`
- `DIGEST_TIMEZONE`, default `America/Phoenix`
- `DIGEST_KEYWORD`, default `python machine learning`
- `SQLITE_PATH`, default `data/goodfirstfindr.db`

## Deployment

The included `render.yaml` deploys with:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Render free tier instances can sleep, so the APScheduler digest only runs while the service is awake. SQLite is also local to the Render instance; use a managed database later if saved issues need durable production storage.
