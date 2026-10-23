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
docker compose up --build -d
```

The first start migrates the database, loads demo data (the Oulu community and Kaleva RSS feeds) and creates a dev admin.

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
(Anthropic, or an offline stub LLM when no key is set), Postgres (SQLite locally),
and optional MinIO/S3 for images.

## Tests

```bash
cd backend && ../.venv/bin/pytest
```
