"""Copy desk: file a finished story for the human editors.

Saves the ``Snippet`` with its Finnish original and translations, the check results the
editor queue shows, any JSN checklist items an editor must confirm, and opens the review
tasks. The verdict decides how the story is presented to people:

* **Ready to send**: no blocking issue. An editor publishes it with one click.
* **Needs review**: at least one blocking issue (listed). An editor reads it in the queue.
"""

from __future__ import annotations

from datetime import timedelta

from django.apps import apps
from django.db import transaction
from django.utils import timezone

from apps.common.choices import SOURCE_LANGUAGE, ReviewStatus
from apps.editorial import checklist
from apps.editorial import services as editorial

from ..graph.text import hashing_embedding, heuristic_reader_needs, is_first_week_topic, topic_tags

EXPIRES_AFTER = {"high": timedelta(days=14), "medium": timedelta(days=7), "low": timedelta(days=3)}


def verdict(issues: list[dict]) -> str:
    return "needs_review" if any(i["blocking"] for i in issues) else "ready"


@transaction.atomic
def file_story(run, story, state: dict):
    Snippet = apps.get_model("feed", "Snippet")
    SnippetVersion = apps.get_model("feed", "SnippetVersion")
    VerificationResult = apps.get_model("editorial", "VerificationResult")
    StandardsCheck = apps.get_model("editorial", "StandardsCheck")
    ChecklistItem = apps.get_model("editorial", "ChecklistItem")

    now = timezone.now()
    src, draft, issues = state["source"], state["draft"], state.get("issues", [])
    risk = state.get("risk") or "medium"
    text = " ".join([src["title"], src["body"], draft["headline"], draft["summary"]])
    level = verdict(issues)
    doc = story.source_document

    snippet = Snippet.objects.create(
        community=run.community,
        tags=topic_tags(text)[:5],
        reader_needs=heuristic_reader_needs(text, risk),
        risk_tier=risk,
        review_status=ReviewStatus.PENDING_REVIEW,
        confidence=1.0 if level == "ready" else 0.5,
        embedding=hashing_embedding(text, 64),
        geo_bbox=run.community.bbox,
        expires_at=now + EXPIRES_AFTER.get(risk, timedelta(days=7)),
        review_by=now + timedelta(days=3) if risk == "high" else None,
        arrival_day_bucket="first_week" if is_first_week_topic(text) else None,
        ai_generated=True,
        created_by_agent_run=run,
        review_level=level,
        review_reasons=issues,
    )
    if doc:
        snippet.source_documents.add(doc)
    version_no = doc.version if doc else 1
    SnippetVersion.objects.create(
        snippet=snippet, language=SOURCE_LANGUAGE, headline=draft["headline"], summary=draft["summary"],
        key_facts=draft["key_facts"], explainer=state.get("explainer") or {}, source_version=version_no,
        review_status=ReviewStatus.PENDING_REVIEW, is_machine_translated=False,
    )
    for lang, v in (state.get("translations") or {}).items():
        SnippetVersion.objects.create(
            snippet=snippet, language=lang, headline=v["headline"], summary=v["summary"], key_facts=v["key_facts"],
            explainer=v.get("explainer") or {}, source_version=version_no,
            review_status=ReviewStatus.PENDING_REVIEW, is_machine_translated=True,
        )

    # What the editor queue shows next to each story.
    facts = [i for i in issues if i["desk"] == "fact_checker"]
    VerificationResult.objects.create(
        snippet=snippet, language=SOURCE_LANGUAGE, passed=not any(i["blocking"] for i in facts),
        confidence=snippet.confidence,
        mismatches=[{"kind": "facts", "value": "", "issue": i["text"], "severity": "error" if i["blocking"] else "warning"} for i in facts],
    )
    std = [i for i in issues if i["desk"] == "standards"]
    StandardsCheck.objects.create(
        snippet=snippet, passed=not any(i["blocking"] for i in std),
        results={i["text"]: "fail" if i["blocking"] else "note" for i in std} or {"all checks": "pass"},
    )
    for key in state.get("sensitive") or []:
        check = checklist.SENSITIVE_CHECKS[key]
        ChecklistItem.objects.create(snippet=snippet, key=key, label=check["label"], clauses=check["clauses"])

    editorial.enqueue(snippet, "new")
    editorial.log(snippet, "drafted", agent="newsroom", payload={
        "run": run.pk, "verdict": level, "reasons": [i["text"] for i in issues if i["blocking"]],
    })
    return snippet
