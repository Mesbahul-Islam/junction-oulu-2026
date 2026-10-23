# Architecture & cross-app contract

This file is the source of truth for model names, key fields and cross-app
references. Apps reference each other's models by **string label**
(`"feed.Snippet"`) to avoid import cycles.

## Layout

```
backend/
  manage.py
  config/            settings.py, urls.py, celery.py, asgi.py, wsgi.py
  apps/
    common/          TimeStampedModel, shared enums (Language, RiskTier, ReaderNeed), permissions
    accounts/        FR-1.1
    communities/     FR-1.2, FR-3.10, FR-3.12, FR-3.14
    feed/            FR-2.x, FR-3.9 storage, FR-3.11
    agents/          FR-3.1–3.3, FR-3.8, FR-3.9 (LangGraph)
    editorial/       FR-3.4–3.7, FR-3.13
    notes/           FR-4
    markets/         FR-5
```

Each app has: `models.py`, `admin.py`, `serializers.py`, `views.py`, `urls.py`,
`services.py` (business logic, no HTTP), `tests/`. Every app's `urls.py` is
mounted at `/api/<app>/` by `config/urls.py`. All models inherit
`apps.common.models.TimeStampedModel` (`created_at`, `updated_at`).

## Shared enums (`apps.common.choices`)

- `Language`: `fi`, `sv`, `en`, `se` (Northern Sámi), `smn` (Inari Sámi), `sms` (Skolt Sámi), `ru`, `uk`, `ar`, `so`, `et`. `SAMI_LANGUAGES = {"se", "smn", "sms"}`.
- `RiskTier`: `high`, `medium`, `low`.
- `ReaderNeed` (Kaleva user-needs): `information`, `understanding`, `usefulness`, `emotion`, `break`, `community`.
- `ReviewStatus`: `draft`, `pending_review`, `changes_requested`, `approved`, `published`, `rejected`, `expired`, `reopened`.
- `ReaderSituation`: `newcomer`, `seasonal_worker`, `student`, `resident`.

## Models

### accounts
- `User(AbstractUser)` — `AUTH_USER_MODEL = "accounts.User"`. Fields: `email` (unique, login field), `display_name`, `preferred_language`, `reader_situation`, `arrival_date` (nullable), `onboarded` (bool), `roles` via `UserRole`.
- `Interest` — taxonomy: `slug`, `name`, `parent` (self FK, nullable).
- `Location` — `name`, `postal_code`, `municipality`, `lat`, `lng`.
- `Profile` — 1:1 `User`; `interests` M2M `Interest`; `location` FK `Location`; `interest_vector` JSON (dict slug→weight).
- `UserRole` — `user`, `role` (`news_editor`, `editor`, `standards_editor`, `language_reviewer`, `community_editor`, `admin`), `language` (nullable), `community` FK `communities.CommunityGroup` (nullable).
- `OnboardingLink` — `code` (unique, used in QR), `community`, `language`, `default_arrival_offset_days` (FR-3.11 QR onboarding).

### communities
- `CommunityGroup` — `name`, `slug`, `kind` (`geo`/`topic`), `municipality`, `bbox` JSON `[min_lng,min_lat,max_lng,max_lat]`, `languages` JSON list, `is_active`.
- `Membership` — `user`, `community`, `role` (`member`/`community_editor`), unique together.
- `Post` — `community`, `author`, `kind` (`announcement`/`post`/`discussion`/`snippet`), `body`, `image`, `parent` (self FK for threads). Visible only to members.
- `CommunityContribution` — FR-3.10/3.12: `community`, `author`, `kind` (`question`/`topic_suggestion`/`tip`/`bridge_story`), `body`, `status` (`new`/`in_review`/`accepted`/`rejected`/`answered`), `contributor_consent` (bool), `named_persons_consent` (bool), `occurrence_count` (for recurring questions), `linked_snippet` FK `feed.Snippet` nullable.
- `SourceFeed` — FR-3.14: `community`, `name`, `url`, `kind` (`rss`/`html`/`api`/`council`), `is_active`, `last_fetched_at`.
- `GlossaryTerm` — `community` (nullable = global), `language`, `term_fi`, `term`, `note`. (Kela, Migri, verokortti …)
- `ContextEntry` — FR-3.8 context library: `community` (nullable), `language`, `topic`, `body`, `valid_from`, `reviewed_at`, `reviewed_by`.
- `FeedbackPrompt` / `FeedbackResponse` — FR-3.10 “what was useful / missing”.

### feed
- `SourceDocument` — raw ingested item: `url`, `title`, `body`, `publisher`, `fetched_at`, `content_hash`, `version` (int), `source_feed` FK `communities.SourceFeed` nullable.
- `Snippet` — language-neutral story record: `community` FK, `source_documents` M2M `SourceDocument`, `tags` JSON list, `reader_needs` JSON list, `risk_tier`, `review_status`, `confidence` (float 0–1), `embedding` JSON list[float], `geo_bbox` JSON, `image` (ImageField, local disk under `MEDIA_ROOT`), `published_at`, `verified_at`, `expires_at`, `review_by`, `arrival_day_bucket` (nullable: `first_48h`/`first_week`/`first_month`), `ai_generated` (bool), `created_by_agent_run` FK `agents.AgentRun` nullable.
- `SnippetVersion` — per-language text (FR-3.9): `snippet`, `language`, `headline`, `summary`, `key_facts` JSON list, `explainer` JSON `{situation: text}`, `background` (text from context library, kept separate), `source_version` (int), `review_status`, `approved_by`, `approved_at`, `is_machine_translated`. Unique (`snippet`, `language`).
- `Interaction` — `user`, `snippet`, `kind` (`like`/`share`/`bookmark`/`expand`/`read_through`/`view`), unique for like/bookmark.
- `Comment` — `user`, `snippet`, `parent`, `body`.
- `SnippetReport` — FR-3.10 “wrong/outdated”: `user`, `snippet`, `reason`, `body`, `resolved`.
- Feed card payload: `id, headline, summary, key_facts, image_url, source_urls, author, tags, published_at, verified_at, review_status, metrics{likes,shares,bookmarks,comments}, ai_disclosure{roles, reviewer, verified_at}, correction_note, community_notes[]`.

### agents
- `AgentRun` — `community`, `trigger` (`schedule`/`manual`/`community_signal`), `status`, `started_at`, `finished_at`, `state` JSON (final LangGraph state), `error`.
- `AgentStep` — `run`, `agent` (`scout`/`assignment`/`synthesizer`/`explainer`/`translator`/`fact_checker`/`standards`/`tagging`), `input` JSON, `output` JSON, `snippet` FK nullable, `duration_ms`.
- Graph in `apps/agents/graph/`: `state.py` (TypedDict), `nodes/*.py` one per agent, `build.py` (`build_graph()`), `llm.py` (provider-agnostic client; Google Gemini Flash by default, deterministic stub when no API key).
- Celery tasks in `apps/agents/tasks.py`: `ingest_and_run(community_id)`, `run_graph_for_sources(community_id, source_ids)`, `expire_snippets()`.
- Persist via `apps.agents.services.persist_graph_result(run, state)` → creates `Snippet` + `SnippetVersion` in `pending_review` and calls `apps.editorial.services.enqueue(snippet, reason=...)`.

### editorial
- `ReviewTask` — `snippet`, `language` (nullable = whole snippet), `required_role`, `priority` (int; flagged/reports first), `reason` (`new`/`flagged_verification`/`failed_standards`/`report`/`low_confidence`/`batch_low_risk`), `status` (`open`/`approved`/`rejected`/`changes_requested`), `assigned_to`, `decided_by`, `decided_at`, `comment`.
- `VerificationResult` — `snippet`, `language`, `passed`, `confidence`, `mismatches` JSON, `back_translation`.
- `StandardsCheck` — `snippet`, `results` JSON `{item: pass/fail/note}`, `passed`.
- `AuditLogEntry` — `snippet`, `actor` (user nullable), `agent` (str nullable), `action`, `payload` JSON.
- `Correction` — `snippet`, `language`, `what_changed`, `approved_by`, `published_at`. Public log endpoint.
- `services.py`: `enqueue`, `required_approvals(snippet)` (risk-tier rules FR-3.7, Sámi rule FR-3.9), `approve`, `reject`, `request_changes`, `can_publish(snippet)`, `publish(snippet)`, `reopen(snippet, reason)`.

### notes
- `CommunityNote` — `snippet` FK nullable, `post` FK `communities.Post` nullable, `author`, `claim_summary`, `context`, `citation_urls` JSON list (≥1), `status` (`needs_more_ratings`/`helpful`/`not_helpful`).
- `NoteRating` — `note`, `rater`, `value` (`helpful`/`somewhat_helpful`/`not_helpful`), `tags` JSON list (≥1). Unique (`note`, `rater`).
- `services.compute_status(note)` — bridging-style: helpful only if helpful ratio ≥ threshold among raters from ≥2 distinct “perspective clusters” (approximated by community + past rating agreement).

### markets (virtual points only)
- `SportEvent` — `sport`, `home`, `away`, `starts_at`, `status`, `final_score` JSON.
- `EventMarket` — `event`, `kind` (`binary`/`fantasy`), `question`, `status` (`open`/`locked`/`resolved`/`void`), `resolution` (`yes`/`no` nullable).
- `Player`, `FantasyContest` (`market`, `salary_cap`, `roster_size`), `FantasyEntry` (`contest`, `user`, `players` M2M, `points`).
- `Position` — `market`, `user`, `side` (`yes`/`no`), `price` Decimal(0.01–1.00), `quantity`, `stake`, `status`.
- `Wallet` — 1:1 user, `balance`, `locked`.
- `LedgerEntry` — double-entry: `transaction_id` (uuid), `wallet`, `amount` (signed), `kind` (`grant`/`stake_lock`/`stake_release`/`payout`/`fee`), `ref`. Sum per transaction_id == 0 (house wallet as counterparty).
- All mutating services use `transaction.atomic()` + `select_for_update()`.

## Celery beat schedule
- `agents.tasks.ingest_all_communities` every 30 min
- `agents.tasks.expire_snippets` every 15 min
- `markets.tasks.settle_finished_events` every 5 min
