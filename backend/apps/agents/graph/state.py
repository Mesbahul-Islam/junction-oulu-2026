"""Shared state passed between the newsroom agents (LangGraph ``StateGraph``).

Everything in here must stay JSON-serialisable (str / int / float / bool /
list / dict / None) because the final state is stored on ``AgentRun.state``.
Dates are ISO-8601 strings.

Per-item dicts are keyed by the item ``key`` (see ``RawItem.key``), e.g.
``"doc:42"`` for a stored ``feed.SourceDocument`` or ``"signal:7"`` for a
``communities.CommunityContribution``.
"""

from __future__ import annotations

from typing import Any, TypedDict


class RawItem(TypedDict, total=False):
    key: str  # "doc:<SourceDocument.pk>" | "signal:<CommunityContribution.pk>" | "mem:<n>" (tests)
    kind: str  # "source" | "community_signal"
    source_document_id: int | None
    contribution_id: int | None
    url: str
    title: str
    body: str
    publisher: str
    fetched_at: str
    content_hash: str
    version: int
    content_type: str  # news | opinion | commercial
    content_marker: str  # what identified it, e.g. "pääkirjoitu", "arvio:"
    # community-signal extras
    contribution_kind: str
    occurrence_count: int
    named_persons_consent: bool
    contributor_consent: bool


class Candidate(TypedDict, total=False):
    key: str
    score: float
    boosted_by: list[str]  # signal keys that boosted this item


class Assignment(TypedDict, total=False):
    reader_needs: list[str]  # ReaderNeed values, >= 1
    risk_tier: str  # RiskTier value
    risk_source: str  # "llm" | "heuristic" | "llm+heuristic_floor"
    expires_at: str
    review_by: str
    arrival_day_bucket: str | None
    rationale: str
    answers_signals: list[str]  # signal keys this source story answers


class Draft(TypedDict, total=False):
    language: str  # always SOURCE_LANGUAGE ("fi")
    headline: str
    summary: str
    key_facts: list[str]
    explainer: dict[str, str]  # ReaderSituation -> "what this means for me"
    background: str  # ONLY from ContextEntry rows, never invented
    background_label: str
    background_context_ids: list[int]


class LanguageVersion(TypedDict, total=False):
    headline: str
    summary: str
    key_facts: list[str]
    explainer: dict[str, str]
    background: str
    is_machine_translated: bool
    needs_human_translation: bool  # Sámi placeholders (FR-3.9)


class Verification(TypedDict, total=False):
    passed: bool
    confidence: float
    mismatches: list[dict[str, Any]]
    back_translation: str


class Standards(TypedDict, total=False):
    results: dict[str, str]  # item -> "pass" | "fail" | "note: ..."
    passed: bool


class Tagging(TypedDict, total=False):
    tags: list[str]
    embedding: list[float]
    geo_bbox: list[float] | None


class StepLogEntry(TypedDict, total=False):
    agent: str
    started_at: str
    duration_ms: int
    summary: dict[str, Any]
    error: str | None


class CommunityInfo(TypedDict, total=False):
    id: int
    name: str
    slug: str
    municipality: str
    bbox: list[float] | None
    languages: list[str]


class NewsroomState(TypedDict, total=False):
    # --- run context -------------------------------------------------------
    run_id: int | None  # AgentRun pk; when absent no AgentStep rows are written
    community_id: int | None
    community: CommunityInfo
    offline: bool  # True => nodes never touch the DB / network (tests, demos)
    fetch: bool  # scout fetches SourceFeeds (False when raw_items given)
    source_ids: list[int]  # restrict scout to these SourceDocument pks
    source_language: str
    language_targets: list[str]  # languages to produce besides source_language
    max_items: int

    # --- community knowledge loaded by scout ------------------------------
    glossary: list[dict[str, Any]]  # {language, term_fi, term, note}
    audience_interests: dict[str, float]  # interest slug -> share of community members who chose it
    context_entries: list[dict[str, Any]]  # {id, language, topic, body}

    # --- pipeline data ------------------------------------------------------
    raw_items: list[RawItem]
    signals: list[RawItem]  # community contributions (also in raw_items)
    candidates: list[Candidate]
    excluded: list[dict[str, Any]]  # opinion / commercial items kept out of the news (JSN 11, 16)
    assignments: dict[str, Assignment]
    drafts: dict[str, Draft]
    translations: dict[str, dict[str, LanguageVersion]]  # key -> lang -> version
    verification: dict[str, dict[str, Verification]]  # key -> lang -> result
    confidence: dict[str, float]  # key -> overall confidence
    standards: dict[str, Standards]
    tags: dict[str, Tagging]

    # --- bookkeeping --------------------------------------------------------
    errors: list[dict[str, Any]]
    step_log: list[StepLogEntry]
