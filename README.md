# junction-oulu-2026

Hyper-local, multilingual news snippets for newcomers and residents, written by a
LangGraph newsroom of AI agents and always approved by a human editor before
publication. It also includes community boards, Community Notes, and a sports
prediction game that uses virtual points only.

**New to the project? Read [docs/GUIDE.md](docs/GUIDE.md).** It explains how everything works.
Model and field names are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Run it

With Docker (recommended):

```bash
cp .env.example .env     # then set LLM_PROVIDER, LLM_MODEL, LLM_API_KEY (e.g. ollama / qwen3:4b, or groq / qwen/qwen3.8-27b / gsk_...)
docker compose up --build -d
```

The AI model is three lines in `.env`; any provider works (local Ollama, Groq, Gemini, OpenAI, Anthropic …; Ollama runs as an optional Docker service). Without them the newsroom runs on an offline stub. The first start migrates the database, loads demo data (the Oulu community and Kaleva RSS feeds) and creates a dev admin.

- **Dev UI: http://localhost:8000/** (feed, compare readers, editor queue, AI newsroom, markets)
- API docs: http://localhost:8000/api/docs/
- Admin: http://localhost:8000/admin/ (`admin@example.com` / `admin`)

Then run the AI newsroom once:

```bash
docker compose exec web python manage.py run_pipeline oulu
```

Without Docker (Python 3.13, SQLite):

```bash
cp .env.example .env
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
cd backend && ../.venv/bin/python manage.py bootstrap && ../.venv/bin/python manage.py runserver
```

`make help` lists shortcuts for all of this. Dependencies are pinned in [backend/requirements.txt](backend/requirements.txt).

## Stack

Django 5.2 + DRF, JWT and Google OAuth, Celery + Redis, LangGraph agents
(model-agnostic: Gemini, OpenAI, Anthropic, local models … chosen per agent; offline stub without a key), Jev (TypeSafe AI)
for feed ranking, Postgres (SQLite locally), and local disk storage for uploaded files.

## Tests

```bash
cd backend && ../.venv/bin/pytest
```
