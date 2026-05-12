# GoodFirstFindr
**Live demo:** https://goodfirstfindr.onrender.com

Find your next open source contribution -- ranked by fit, not just keywords.

![Build](https://img.shields.io/badge/build-passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.11.11-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## What it does

Finding a useful first open source issue is noisy. Popular repository issues can get claimed quickly, issues in the wrong language waste time, and the `good first issue` label does not guarantee the work is a good fit for your skills.

GoodFirstFindr searches GitHub for open, unassigned issues labeled `good first issue`, then runs each candidate through a four-dimension scoring pipeline: skill match, repo health, competition, and freshness. After that, Groq with Llama 3 reads the actual issue description to detect language mismatches, claimed work, unclear requirements, and other red flags that metadata alone can miss.

The result is a ranked list of issues with scores, per-issue explanations, matched skills, and red flags. The app also supports saving issues locally and sending a daily email digest of recommended issues.

## Architecture diagram

```text
GitHub API
    |
    v
Issue Fetcher
    |
    v
Rule-based Filters
    |
    v
Scoring Engine
    |
    v
Groq LLM
    |
    v
Ranked Results
    |
    v
Email Digest
```

| Component | Role |
| --- | --- |
| GitHub API | Searches public GitHub issues with `is:issue`, `is:open`, `label:"good first issue"`, `no:assignee`, and `-linked:pr` when supported. |
| Issue Fetcher | Uses `httpx` to fetch matching issues and repository metadata such as stars, forks, language, open issue count, and recent activity. |
| Rule-based Filters | Removes pull requests, assigned issues, and issues with assignees from the candidate set. |
| Scoring Engine | Calculates skill match, repo health, competition, and freshness scores, then combines them into an initial 0-100 score. |
| Groq LLM | Reads issue descriptions with a Python-heavy ML/backend skill profile and returns a fit score, primary language, red flags, and explanation. |
| Ranked Results | Blends the rule-based score with the LLM fit score, applies penalties, sorts candidates, and returns API/UI results. |
| Email Digest | Uses APScheduler and Gmail SMTP to send the top daily recommendations for the configured keyword. |

## Scoring breakdown

| Dimension | Weight | What it measures |
| --- | ---: | --- |
| Skill match | 40% | Matches issue title, body, labels, repository metadata, language, and topics against the hardcoded ML/backend skill profile. |
| Repo health | 25% | Scores repository activity, stars, forks, and open issue load. |
| Competition | 20% | Favors issues with fewer comments, since fewer comments often means less visible competition. |
| Freshness | 15% | Rewards issues that are recent enough to still be active without only favoring issues from the last few hours. |

The scoring engine first computes:

```text
rule_based_score =
  (skill_match * 0.40) +
  (repo_health * 0.25) +
  (competition * 0.20) +
  (freshness * 0.15)
```

When LLM explanations are enabled, GoodFirstFindr blends the deterministic score 50/50 with the Groq fit score:

```text
blended_score = (rule_based_score * 0.50) + (llm_fit_score * 0.50)
```

Then it subtracts penalties:

- Language penalty: 40 points if the LLM says the primary language is not `python` or `any`.
- Red flag penalty: 15 points per red flag, capped at 50 points.

Final scores are clamped to a minimum of 0 and rounded to one decimal place.

## Tech stack

- FastAPI
- httpx
- Groq API with Llama 3.3 70B (`llama-3.3-70b-versatile`)
- APScheduler
- SQLite
- Jinja2
- Render

## Local setup

Prerequisite: Python 3.11.11. The repository includes `.python-version` for tools such as pyenv and Render.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn main:app --reload
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

Environment variables from `.env.example`:

| Variable | Description |
| --- | --- |
| `GITHUB_TOKEN` | GitHub personal access token used for higher API rate limits and authenticated issue search. |
| `GROQ_API_KEY` | Groq API key used to generate fit scores, red flags, and issue explanations. |
| `GROQ_MODEL` | Groq model name. Defaults to `llama-3.3-70b-versatile`. |
| `GMAIL_USER` | Gmail address used to send the daily digest. |
| `GMAIL_APP_PASSWORD` | Gmail app password for SMTP authentication. |
| `RECIPIENT_EMAIL` | Email address that receives the daily digest. |
| `DIGEST_ENABLED` | Enables or disables the APScheduler daily digest. Defaults to `true`. |
| `DIGEST_TIME` | Local digest time in `HH:MM` format. Defaults to `08:00`. |
| `DIGEST_TIMEZONE` | Time zone for the digest schedule. Defaults to `America/Phoenix`. |
| `DIGEST_KEYWORD` | Search keyword used for the daily digest. Defaults to `python machine learning`. |
| `SQLITE_PATH` | SQLite database path for saved issues. Defaults to `data/goodfirstfindr.db`. |

The app can run without `GROQ_API_KEY`; in that case it uses deterministic fallback explanations. The daily digest is skipped unless the Gmail and recipient variables are configured.

## Deployment

The repository includes `render.yaml` for Render:

```yaml
buildCommand: pip install -r requirements.txt
startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
```

Render deployment steps:

1. Push the repository to GitHub.
2. Create a new Render Blueprint or Web Service from the repository.
3. Ensure the service uses Python `3.11.11`. Keep `.python-version` committed so local and hosted runtimes stay aligned.
4. Add the required secrets in Render: `GITHUB_TOKEN`, `GROQ_API_KEY`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`, and `RECIPIENT_EMAIL`.
5. Deploy the service and check `/healthz` after startup.

Render free tier instances can sleep, so the APScheduler digest only runs while the service is awake. SQLite storage is local to the Render instance and should be treated as ephemeral; use PostgreSQL or another managed database for durable production storage.

## Roadmap

- [ ] Persistent PostgreSQL storage
- [ ] Dynamic user skill profiles
- [ ] Fine-tuned ranking model trained on save/dismiss feedback
- [ ] Multi-user support with auth

## Contributing

Contributions are welcome, especially fixes that improve ranking quality, issue filtering, deployment docs, or test coverage. Please [open an issue](https://github.com/Animesh452/GoodFirstFindr/issues) with the bug or proposal, then send a focused pull request linked to that issue.
