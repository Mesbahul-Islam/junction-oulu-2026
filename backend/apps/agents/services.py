"""Business logic for agent runs (no HTTP).

* ``start_run`` / ``execute_run`` - run the LangGraph newsroom for an AgentRun.
* ``persist_graph_result(run, state)`` - turn the final graph state into
  ``feed.Snippet`` + ``feed.SnippetVersion`` (all ``pending_review``),
  ``editorial.VerificationResult``, ``editorial.StandardsCheck`` and an
  editorial review-queue entry. **Nothing is ever published here** (FR-3.4);
  publishing is exclusively ``apps.editorial.services.publish``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.common.choices import SOURCE_LANGUAGE, ReviewStatus, RiskTier

from .graph.build import build_graph, json_safe
from .graph.state import NewsroomState
from .models import AgentRun

logger = logging.getLogger(__name__)

AGENT_NAME = "newsroom_graph"


def _threshold() -> float:
    return float(getattr(settings, "AGENT_CONFIDENCE_THRESHOLD", 0.7))


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if timezone.is_aware(dt) else timezone.make_aware(dt)


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------


def initial_state(run: AgentRun, *, source_ids: list[int] | None = None, fetch: bool = True, **extra) -> NewsroomState:
    state: NewsroomState = {
        "run_id": run.pk,
        "community_id": run.community_id,
        "offline": False,
        "fetch": fetch,
        "source_language": SOURCE_LANGUAGE.value,
        "errors": [],
        "step_log": [],
    }
    if source_ids:
        state["source_ids"] = list(source_ids)
    state.update(extra)  # e.g. language_targets, max_items
    return state


def execute_run(run: AgentRun, state: NewsroomState) -> list:
    """Run the graph for ``run`` and persist the results. Returns created snippets."""
    run.status = AgentRun.Status.RUNNING
    run.started_at = timezone.now()
    run.error = ""
    run.save(update_fields=["status", "started_at", "error", "updated_at"])
    try:
        final = build_graph().invoke(state)
        snippets = persist_graph_result(run, final)
    except Exception as exc:
        logger.exception("Agent run %s failed", run.pk)
        run.status = AgentRun.Status.FAILED
        run.error = f"{type(exc).__name__}: {exc}"[:5000]
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error", "finished_at", "updated_at"])
        raise
    run.status = AgentRun.Status.SUCCEEDED
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "finished_at", "updated_at"])
    return snippets


# ---------------------------------------------------------------------------
# Persisting
# ---------------------------------------------------------------------------


def review_reason(*, verification_passed: bool, standards_passed: bool, confidence: float, risk_tier: str) -> str:
    """Pick the editorial queue reason (highest-priority problem first)."""
    if not verification_passed:
        return "flagged_verification"
    if not standards_passed:
        return "failed_standards"
    if confidence < _threshold():
        return "low_confidence"
    if risk_tier == RiskTier.LOW.value:
        return "batch_low_risk"
    return "new"


def persist_graph_result(run: AgentRun, state: NewsroomState) -> list:
    """Create Snippet/SnippetVersion/VerificationResult/StandardsCheck rows and
    enqueue every snippet for human review. Returns the created snippets."""
    from apps.editorial import services as editorial

    Snippet = apps.get_model("feed", "Snippet")
    SnippetVersion = apps.get_model("feed", "SnippetVersion")
    VerificationResult = apps.get_model("editorial", "VerificationResult")
    StandardsCheck = apps.get_model("editorial", "StandardsCheck")
    SourceDocument = apps.get_model("feed", "SourceDocument")
    Contribution = apps.get_model("communities", "CommunityContribution")

    raw = {r["key"]: r for r in state.get("raw_items") or []}
    assignments = state.get("assignments") or {}
    translations = state.get("translations") or {}
    verification = state.get("verification") or {}
    confidence_map = state.get("confidence") or {}
    standards = state.get("standards") or {}
    tags = state.get("tags") or {}
    threshold = _threshold()
    created = []

    for key, draft in (state.get("drafts") or {}).items():
        item = raw.get(key, {})
        assignment = assignments.get(key, {})
        ver = verification.get(key, {})
        std = standards.get(key, {"results": {}, "passed": False})
        tag = tags.get(key, {})
        confidence = float(confidence_map.get(key, 0.0))
        verification_passed = bool(ver) and all(v.get("passed") for v in ver.values())

        risk = assignment.get("risk_tier") or RiskTier.MEDIUM.value
        escalated = False
        if not verification_passed or confidence < threshold:
            escalated = risk != RiskTier.HIGH.value
            risk = RiskTier.HIGH.value  # FR-3.7: doubtful content gets the strictest review

        source_version = int(item.get("version") or 0)
        try:
            with transaction.atomic():
                snippet = Snippet.objects.create(
                    community_id=state.get("community_id") or run.community_id,
                    tags=tag.get("tags", []),
                    reader_needs=assignment.get("reader_needs") or ["information"],
                    risk_tier=risk,
                    review_status=ReviewStatus.PENDING_REVIEW,
                    confidence=confidence,
                    embedding=tag.get("embedding", []),
                    geo_bbox=tag.get("geo_bbox"),
                    expires_at=_dt(assignment.get("expires_at")),
                    review_by=_dt(assignment.get("review_by")),
                    arrival_day_bucket=assignment.get("arrival_day_bucket"),
                    ai_generated=True,
                    created_by_agent_run=run,
                )
                if item.get("source_document_id"):
                    snippet.source_documents.set(SourceDocument.objects.filter(pk=item["source_document_id"]))

                # Source-language version (fi)
                src_lang = draft.get("language") or SOURCE_LANGUAGE.value
                SnippetVersion.objects.create(
                    snippet=snippet,
                    language=src_lang,
                    headline=draft.get("headline", "")[:300],
                    summary=draft.get("summary", ""),
                    key_facts=draft.get("key_facts", []),
                    explainer=draft.get("explainer", {}),
                    background=draft.get("background", ""),
                    source_version=source_version,
                    review_status=ReviewStatus.PENDING_REVIEW,
                    is_machine_translated=False,
                )
                needs_human = []
                for lang, v in translations.get(key, {}).items():
                    placeholder = bool(v.get("needs_human_translation"))
                    if placeholder:
                        needs_human.append(lang)
                    SnippetVersion.objects.create(
                        snippet=snippet,
                        language=lang,
                        headline=v.get("headline", "")[:300],
                        summary=v.get("summary", ""),
                        key_facts=v.get("key_facts", []),
                        explainer=v.get("explainer", {}),
                        background=v.get("background", ""),
                        source_version=source_version,
                        # Sámi placeholder stays a draft until a human translator writes it (FR-3.9)
                        review_status=ReviewStatus.DRAFT if placeholder else ReviewStatus.PENDING_REVIEW,
                        is_machine_translated=bool(v.get("is_machine_translated")) and not placeholder,
                    )

                for lang, v in ver.items():
                    VerificationResult.objects.create(
                        snippet=snippet,
                        language=lang,
                        passed=bool(v.get("passed")),
                        confidence=float(v.get("confidence") or 0.0),
                        mismatches=json_safe(v.get("mismatches", [])),
                        back_translation=v.get("back_translation", ""),
                    )
                StandardsCheck.objects.create(snippet=snippet, results=std.get("results", {}), passed=bool(std.get("passed")))

                # Link community contributions this snippet answers / came from.
                contribution_ids = [item["contribution_id"]] if item.get("contribution_id") else []
                contribution_ids += [
                    int(s.split(":", 1)[1]) for s in assignment.get("answers_signals", []) if s.startswith("signal:")
                ]
                if contribution_ids:
                    Contribution.objects.filter(pk__in=contribution_ids, linked_snippet__isnull=True).update(
                        linked_snippet=snippet, status="in_review"
                    )

                reason = review_reason(
                    verification_passed=verification_passed,
                    standards_passed=bool(std.get("passed")),
                    confidence=confidence,
                    risk_tier=risk,
                )
                editorial.log(
                    snippet,
                    "agent_created",
                    agent=AGENT_NAME,
                    payload=json_safe({
                        "run_id": run.pk,
                        "item_key": key,
                        "risk_tier": risk,
                        "risk_escalated": escalated,
                        "risk_source": assignment.get("risk_source"),
                        "confidence": confidence,
                        "review_reason": reason,
                        "needs_human_translation": needs_human,
                    }),
                )
                editorial.enqueue(snippet, reason)
                # Per-language tasks (incl. human translation of Sámi placeholders, FR-3.9)
                # are derived by editorial.required_approvals() from the versions created above.
        except Exception as exc:  # one bad item must not lose the others
            logger.exception("Persisting %s of run %s failed", key, run.pk)
            state.setdefault("errors", []).append({"agent": "persist", "item": key, "error": str(exc)[:1000]})
            continue
        created.append(snippet)

    if len(created) == 1:
        run.steps.filter(snippet__isnull=True).update(snippet=created[0])

    run.state = json_safe(state)
    run.save(update_fields=["state", "updated_at"])
    return created


# ---------------------------------------------------------------------------
# Expiry (FR-3.13 / freshness)
# ---------------------------------------------------------------------------


def expire_snippets(now: datetime | None = None) -> dict[str, int]:
    from apps.editorial import services as editorial

    Snippet = apps.get_model("feed", "Snippet")
    now = now or timezone.now()
    expired_qs = Snippet.objects.filter(review_status=ReviewStatus.PUBLISHED, expires_at__lt=now)
    expired = 0
    for snippet in expired_qs:
        snippet.review_status = ReviewStatus.EXPIRED
        snippet.save(update_fields=["review_status", "updated_at"])
        editorial.log(snippet, "expired", agent=AGENT_NAME, payload={"expires_at": snippet.expires_at.isoformat()})
        expired += 1

    # Published but past review_by: ask a human to re-check facts.
    # TODO: re-run the agents against the latest SourceDocument version.
    refreshed = 0
    stale = Snippet.objects.filter(review_status=ReviewStatus.PUBLISHED, review_by__lt=now)
    for snippet in stale:
        editorial.enqueue(snippet, "refresh")
        snippet.review_by = None  # avoid re-enqueueing every 15 minutes
        snippet.save(update_fields=["review_by", "updated_at"])
        refreshed += 1
    return {"expired": expired, "refresh_enqueued": refreshed}

