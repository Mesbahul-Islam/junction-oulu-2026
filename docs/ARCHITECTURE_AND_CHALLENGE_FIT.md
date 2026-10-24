# Architecture & Challenge Fit

How the backend is built, and how it maps to the Junction Oulu 2026 challenge
(a multilingual news medium run by AI agents, built *with and for* a community).

---

## 1. System at a glance

- **Django 5.2 + Django REST Framework.** The backend is a JSON API under `/api/`.
- **Two HTML admin pages** are served as plain static files (not Django templates):
  - `backend/frontend/index.html` — the **AI Newsroom admin** (main dev tool).
  - `backend/frontend/fantasy.html` — a small Fantasy Liiga UI.
- **A separate React phone app** (not in this repo) is the reader-facing product. It calls the same API.
- **Celery + Redis** run background jobs (newsroom shifts, snippet expiry).
- **SQLite** by default; switch to PostgreSQL via `DATABASE_URL`.
- **JWT** secures the API (no login cookies). **CORS** lets the React app call from another origin.

### Project layout

```
backend/
  config/        settings.py, urls.py, celery.py
  apps/
    accounts/    users, Google OAuth, JWT
    feed/        snippets, per-language versions, personal feed, Jev ranker
    agents/      the AI newsroom (LangGraph desks)
    editorial/   human review queue, standards checklist, audit log, corrections
    communities/ community groups, posts, questions, moderation, glossary
    notes/       Community Notes on snippets and posts
    markets/     sports prediction markets (virtual points only)
    fantasy/     season-long Fantasy Liiga
    common/      shared choices, base models, pagination
```

Each app follows the same shape: `models.py`, `views.py`, `serializers.py`,
`urls.py`, `services.py`, `tasks.py`.

---

## 2. How a request flows

1. A browser hits a URL. `config/urls.py` routes it.
2. `/` and `/fantasy/` return an **HTML file**. `/admin/` is the built-in Django admin.
   `/api/.../` returns **JSON** from an app.
3. For an API URL: a **view** reads the DB via **models**, a **serializer** turns it into JSON, the view returns it.

### The HTML admin is a thin client

- `frontend/index.html` is **one static file** (HTML + CSS + JS together). Django just reads it from disk.
- All logic is browser JavaScript. It talks to the API via one `fetch` helper (`index.html:258`).
- Login: `POST /api/auth/token/` returns a JWT; the page stores it in `localStorage` and sends it in the
  `Authorization` header on every call. Non-staff users are rejected (`is_staff` check).
- Key endpoints it reads: `/api/agents/dashboard/`, `/api/agents/runs/`, `/api/editorial/tasks/`,
  `/api/communities/moderation/`.

> **LangChain and Jev run in Python on the server, never in the browser.** The HTML only *displays*
> their results (e.g. a Jev score bar). Deleting the HTML would not stop the newsroom from running.

---

## 3. The AI newsroom (core feature — `agents` app)

A **shift** is one `AgentRun`. It starts **manually** (a button → `POST /api/agents/runs/`) or on a
**schedule** (Celery every `AGENT_SCHEDULE_MINUTES`, default 30). A shift runs in the background and
returns `202 Accepted` immediately; the admin polls `/api/agents/runs/<id>/` for live progress.

Inside a shift, each story moves through desks in order (`agents/newsroom/runner.py`):

```
wire → news editor (Jev + member votes) → reporter → explainer → translator
     → fact-checker → standards editor → copy desk → community vote → HUMAN EDITORS
```

- Desks are AI agents built on **LangGraph / LangChain**. The LLM provider is set in `.env`
  (`LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`); empty = an offline stub.
- Every desk writes an `AgentStep` to the DB, which is what the dashboard's live view shows.
- **The newsroom never publishes on its own.** It marks stories "Ready to send"; a human clicks to
  publish, and their name goes in the audit log (`agents/services.py:send_story`).

---

## 4. Challenge fit

| Challenge item | Status | Evidence |
|---|---|---|
| Agentic newsroom modeled on a real newsroom | **Strong** | `agents/models.py` DESKS mirror real newsroom roles |
| Human always in the loop | **Strong** | `editorial` review queue; publish requires a person; audit log |
| Follow JSN Journalist's Guidelines | **Yes** | `STANDARDS_CHECKLIST` + `checklist.py` map checks to JSN clauses |
| Explanatory journalism (not plain translation) | **Yes** | `SnippetVersion.explainer = {reader_situation: text}` |
| Reader situations (newcomer, seasonal worker, student) | **Yes** | `ReaderSituation` enum |
| Kaleva user-needs model (all 6 needs) | **Yes** | `ReaderNeed` enum |
| Community decides what matters | **Strong** | Shortlist voting, `CoverageCandidate` / `CoverageVote` |
| Community contributes & corrects | **Yes** | `CommunityContribution` (questions → stories), Community Notes, corrections log |
| Supporting Sámi languages | **Strong** | `SAMI_LANGUAGES` are **never** machine-translated; human translator required |
| Quality / error control for high-risk news | **Strong** | `RiskTier` (residence/health/employment = high), fact-checker, `review_by` recheck |
| Trust / open AI disclosure | **Yes** | `ai_role_disclosed` check, reader-report path, public corrections |
| Relevance personalization | **Yes** | Jev re-ranks per situation/language/interests (`feed/jev.py`) |
| Bridge to Finnish-speaking audience | **Partial** | 12 languages, but no explicit "about-the-community, for Finns" flow |
| Short life cycle (seasonal workers) | **Partial** | `expires_at` + `seasonal_worker` exist; no "reach on arrival, in time" flow |
| **Business model** | **Not built** | Pitch material — see `BUSINESS_MODEL.md` |
| Distribution beyond the app | **Thin** | App + audio (`ListenPlayer`); no messaging apps / short-form video |

### Languages supported (`common/choices.py`)

Finnish (source), Swedish, English, North Sámi, Inari Sámi, Skolt Sámi, Russian, Ukrainian,
Arabic, Somali, Estonian. Sámi languages are flagged so AI output is never published in them.

---

## 5. Gaps & risks

1. **Business model is not in code** (expected — it's a pitch deliverable). See `BUSINESS_MODEL.md`.
2. **Distribution is thin.** Only the app + audio exist. The challenge explicitly asks for the channels
   communities already use (messaging apps, short-form video). This is the biggest reach gap.
3. **Short life cycle is only partial.** No onboarding / time-boxed feed to catch a seasonal worker on arrival.
4. **JSN checklist wording is a `TODO`** (`editorial/models.py:11`) — confirm against the real guidelines.
5. **Possible scope creep:** the `markets` (prediction markets) and `fantasy` (Fantasy Liiga) apps are
   sports-engagement features, off the multilingual-news core. They add two apps + the Liiga API. Consider
   leaving them out of the core demo so the message stays focused.

---

## 6. Verdict

The **technology and journalism** sides match the challenge well — arguably beyond a prototype
(newsroom pipeline, human-in-loop, Sámi safeguards, community voting). The **business model** and
**distribution beyond the app** are the weak points, and they are exactly what the judges said they value.
