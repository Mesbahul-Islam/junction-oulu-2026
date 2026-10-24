"""Editorial workflow (FR-3.4–3.7, FR-3.9 Sámi rule, FR-3.13 audit/corrections).

Approval model
--------------
`required_approvals(snippet)` returns a list of `Requirement(role, language)`;
`language=None` means the whole snippet (all language versions).

* Every snippet → one editor, plus one language_reviewer per non-Finnish language version
  (an editor can't vouch for a translation they can't read; FR-3.9, JSN clause 9).
* The risk tier sets priority; Low is queued as `batch_low_risk` (still a human approval).
* Failed verification or confidence < AGENT_CONFIDENCE_THRESHOLD escalates to High.
* Sámi versions (FR-3.9) always need a language_reviewer and must have
  is_machine_translated=False; a community_editor of the snippet's community may veto.

Gating is per language: the snippet is publishable once all whole-snippet requirements
are approved and the Finnish source version is approved; every other language version
becomes visible only when its own requirements are approved (feed shows approved versions only).
"""

from typing import NamedTuple

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.common.permissions import has_role
from apps.common.choices import SAMI_LANGUAGES, SOURCE_LANGUAGE, ReviewStatus, RiskTier
from apps.feed.models import SnippetVersion

from .models import AuditLogEntry, ChecklistItem, Correction, ReviewTask, VerificationResult

EDITOR = "editor"
LANGUAGE_REVIEWER = "language_reviewer"
COMMUNITY_EDITOR = "community_editor"

TOP_PRIORITY = 100
REASON_PRIORITY = {
    ReviewTask.Reason.REPORT: 90,
    ReviewTask.Reason.FLAGGED_VERIFICATION: 80,
    ReviewTask.Reason.FAILED_STANDARDS: 70,
    ReviewTask.Reason.LOW_CONFIDENCE: 60,
    ReviewTask.Reason.NEW: 0,
    ReviewTask.Reason.BATCH_LOW_RISK: 0,
}
TIER_PRIORITY = {RiskTier.HIGH: 30, RiskTier.MEDIUM: 20, RiskTier.LOW: 10}
EDITABLE_FIELDS = {"headline", "summary", "key_facts", "explainer", "background", "is_machine_translated"}


class Requirement(NamedTuple):
    role: str
    language: str | None = None


# --- pure rules ---------------------------------------------------------------


def should_escalate(confidence: float, verification_failed: bool) -> bool:
    return verification_failed or confidence < settings.AGENT_CONFIDENCE_THRESHOLD


def effective_tier(risk_tier: str, confidence: float, verification_failed: bool) -> str:
    return RiskTier.HIGH if should_escalate(confidence, verification_failed) else risk_tier


def requirements_for(tier: str, languages) -> list[Requirement]:
    """Approvals a snippet needs (pure).

    Always one editor for the story, plus a reviewer *who reads that language* for every
    translated version (FR-3.9, JSN clause 9), whatever the risk tier: an editor can't
    vouch for an Arabic text they can't read. The tier still sets queue priority, batch
    approval for low risk, and expiry. Sámi versions are written by a human anyway.
    """
    langs = sorted(set(languages) - {SOURCE_LANGUAGE})
    return [Requirement(EDITOR)] + [Requirement(LANGUAGE_REVIEWER, lang) for lang in langs]


def requirements_met(reqs, approved: set, language: str | None = None) -> bool:
    """All requirements covering `language` (whole-snippet ones always apply) are in `approved`."""
    return all(r in approved for r in reqs if r.language is None or r.language == language)


# --- helpers ------------------------------------------------------------------


def _verification_failed(snippet) -> bool:
    latest = {}
    for v in VerificationResult.objects.filter(snippet=snippet).order_by("created_at"):
        latest[v.language] = v.passed
    return any(passed is False for passed in latest.values())


def _snippet_tier(snippet) -> str:
    return effective_tier(snippet.risk_tier, snippet.confidence, _verification_failed(snippet))


def _active_tasks(snippet):
    return ReviewTask.objects.filter(snippet=snippet, active=True)


def _approved_set(snippet) -> set:
    return {
        Requirement(t.required_role, t.language)
        for t in _active_tasks(snippet).filter(status=ReviewTask.Status.APPROVED)
    }


def can_decide(user, task) -> bool:
    return has_role(user, task.required_role, language=task.language, community=task.snippet.community_id)


def can_veto(user, task) -> bool:
    """FR-3.9: community_editor of the snippet's community may veto Sámi-language content."""
    if task.language not in SAMI_LANGUAGES or task.snippet.community_id is None:
        return False
    return user.roles.filter(role=COMMUNITY_EDITOR, community_id=task.snippet.community_id).exists()


def _check_open(task):
    if not task.active or task.status != ReviewTask.Status.OPEN:
        raise ValidationError("Task is not open.")


def _sync_versions(snippet, user):
    """Mark language versions approved once their requirements are met (FR-3.9 Sámi guard)."""
    reqs = required_approvals(snippet)
    approved = _approved_set(snippet)
    now = timezone.now()
    for v in snippet.versions.all():
        if v.review_status in (ReviewStatus.APPROVED, ReviewStatus.PUBLISHED):
            continue
        if v.language in SAMI_LANGUAGES and v.is_machine_translated:
            continue
        if requirements_met(reqs, approved, v.language):
            v.review_status, v.approved_by, v.approved_at = ReviewStatus.APPROVED, user, now
            v.save(update_fields=["review_status", "approved_by", "approved_at", "updated_at"])


def _release_corrections(snippet, now):
    Correction.objects.filter(snippet=snippet, published_at__isnull=True).update(published_at=now)


def _apply_edits(snippet, language, edits, user):
    """Apply editor edits to one language version; edits on a published snippet create a Correction."""
    unknown = set(edits) - EDITABLE_FIELDS - {"correction_note"}
    if unknown:
        raise ValidationError(f"Non-editable fields: {sorted(unknown)}")
    version = snippet.versions.get(language=language or SOURCE_LANGUAGE)
    changed = {k: v for k, v in edits.items() if k in EDITABLE_FIELDS and getattr(version, k) != v}
    for k, v in changed.items():
        setattr(version, k, v)
    if changed:
        version.save()
        if snippet.published_at:
            Correction.objects.create(
                snippet=snippet,
                language=version.language,
                what_changed=edits.get("correction_note") or f"Updated: {', '.join(sorted(changed))}",
                approved_by=user,
            )
        log(snippet, "edited", actor=user, payload={"language": version.language, "fields": sorted(changed)})
    return version


# --- public API ---------------------------------------------------------------


def log(snippet, action, actor=None, agent=None, payload=None) -> AuditLogEntry:
    """FR-3.13: append an audit entry. Every service action calls this."""
    return AuditLogEntry.objects.create(
        snippet=snippet, actor=actor, agent=agent, action=action, payload=payload or {}
    )


def required_approvals(snippet) -> list[Requirement]:
    languages = list(snippet.versions.values_list("language", flat=True)) or [SOURCE_LANGUAGE]
    return requirements_for(_snippet_tier(snippet), languages)


def _create_tasks(snippet, reason, language=None, priority=None):
    tier = _snippet_tier(snippet)
    if reason == ReviewTask.Reason.NEW:
        if _verification_failed(snippet):
            reason = ReviewTask.Reason.FLAGGED_VERIFICATION
        elif snippet.confidence < settings.AGENT_CONFIDENCE_THRESHOLD:
            reason = ReviewTask.Reason.LOW_CONFIDENCE
        elif tier == RiskTier.LOW:
            reason = ReviewTask.Reason.BATCH_LOW_RISK
    if priority is None:
        priority = REASON_PRIORITY.get(reason, 0) + TIER_PRIORITY.get(tier, 0)
    reqs = required_approvals(snippet)
    if language is not None:
        reqs = [r for r in reqs if r.language == language]
    existing = {Requirement(t.required_role, t.language) for t in _active_tasks(snippet).exclude(status="rejected")}
    return [
        ReviewTask.objects.create(
            snippet=snippet, language=r.language, required_role=r.role, reason=reason, priority=priority
        )
        for r in reqs
        if r not in existing
    ]


@transaction.atomic
def enqueue(snippet, reason, language=None) -> list[ReviewTask]:
    """FR-3.4: open review tasks for every missing requirement (optionally one language)."""
    tasks = _create_tasks(snippet, reason, language)
    if language is None and snippet.review_status not in (ReviewStatus.PUBLISHED, ReviewStatus.REOPENED):
        snippet.review_status = ReviewStatus.PENDING_REVIEW
        snippet.save(update_fields=["review_status", "updated_at"])
    log(snippet, "enqueued", payload={"reason": reason, "language": language, "tasks": [t.pk for t in tasks]})
    return tasks


def pending_checklist(snippet):
    """Sensitive-topic checks (JSN crime, right of reply, minors, illness/death) not yet confirmed."""
    return ChecklistItem.objects.filter(snippet=snippet, confirmed_at__isnull=True)


def confirm_checklist(snippet, user, keys, notes=None) -> list[str]:
    """Record the editor's confirmation of the given checklist items. Returns the keys confirmed."""
    notes = notes or {}
    done = []
    for item in pending_checklist(snippet).filter(key__in=list(keys or [])):
        item.confirmed_by, item.confirmed_at, item.note = user, timezone.now(), notes.get(item.key, "")
        item.save(update_fields=["confirmed_by", "confirmed_at", "note", "updated_at"])
        done.append(item.key)
    if done:
        log(snippet, "checklist_confirmed", actor=user, payload={"items": done})
    return done


@transaction.atomic
def approve(task, user, edits=None, confirm=None, notes=None) -> ReviewTask:
    """Approve one review task. The editor's whole-story approval must also confirm every
    open sensitive-topic checklist item (``confirm`` = their keys); otherwise it is refused."""
    _check_open(task)
    if not can_decide(user, task):
        raise PermissionDenied("Missing required role for this task.")
    snippet = task.snippet
    if task.language is None:
        confirm_checklist(snippet, user, confirm, notes)
        missing = list(pending_checklist(snippet).values_list("key", flat=True))
        if missing:
            raise ValidationError(f"Confirm the editorial checklist before approving: {', '.join(missing)}.")
    if edits:
        _apply_edits(snippet, task.language, edits, user)
    if task.language in SAMI_LANGUAGES and snippet.versions.filter(
        language=task.language, is_machine_translated=True
    ).exists():
        raise ValidationError("FR-3.9: machine-translated Sámi text cannot be approved; supply a human translation.")
    if task.language and snippet.versions.filter(language=task.language, headline="").exists():
        # Sámi placeholders start empty: the reviewer must write the text (via `edits`) before approving.
        raise ValidationError(f"The {task.language} version has no text yet; include it in `edits` to approve.")
    task.status, task.decided_by, task.decided_at = ReviewTask.Status.APPROVED, user, timezone.now()
    task.save()
    log(snippet, "approved", actor=user, payload={"task": task.pk, "role": task.required_role, "language": task.language})
    _sync_versions(snippet, user)
    if snippet.review_status != ReviewStatus.PUBLISHED and can_publish(snippet):
        publish(snippet)
    elif snippet.review_status == ReviewStatus.PUBLISHED:
        _release_corrections(snippet, timezone.now())
    return task


@transaction.atomic
def reject(task, user, comment) -> ReviewTask:
    _check_open(task)
    decide = can_decide(user, task)
    veto = not decide and can_veto(user, task)
    if not (decide or veto):
        raise PermissionDenied("Missing required role for this task.")
    snippet = task.snippet
    task.status, task.decided_by, task.decided_at, task.comment = (
        ReviewTask.Status.REJECTED, user, timezone.now(), comment,
    )
    task.save()
    if task.language is None:
        snippet.review_status = ReviewStatus.REJECTED
        snippet.save(update_fields=["review_status", "updated_at"])
    else:
        SnippetVersion.objects.filter(snippet=snippet, language=task.language).update(
            review_status=ReviewStatus.REJECTED
        )
    log(snippet, "vetoed" if veto else "rejected", actor=user, payload={"task": task.pk, "comment": comment})
    return task


@transaction.atomic
def request_changes(task, user, comment) -> ReviewTask:
    _check_open(task)
    if not can_decide(user, task):
        raise PermissionDenied("Missing required role for this task.")
    snippet = task.snippet
    task.status, task.decided_by, task.decided_at, task.comment = (
        ReviewTask.Status.CHANGES_REQUESTED, user, timezone.now(), comment,
    )
    task.save()
    if task.language is None:
        snippet.review_status = ReviewStatus.CHANGES_REQUESTED
        snippet.save(update_fields=["review_status", "updated_at"])
    else:
        SnippetVersion.objects.filter(snippet=snippet, language=task.language).update(
            review_status=ReviewStatus.CHANGES_REQUESTED
        )
    log(snippet, "changes_requested", actor=user, payload={"task": task.pk, "comment": comment})
    # TODO: trigger agent revision run (apps.agents) and re-enqueue when the new draft lands.
    return task


def can_publish(snippet) -> bool:
    """Whole-snippet requirements approved, no active veto/rejection, source version approvable."""
    if snippet.review_status in (ReviewStatus.REJECTED, ReviewStatus.EXPIRED):
        return False
    if snippet.expires_at and snippet.expires_at < timezone.now():
        return False
    if pending_checklist(snippet).exists():  # JSN sensitive topics need an editor's explicit confirmation
        return False
    active = _active_tasks(snippet)
    if active.filter(language__isnull=True).exclude(status=ReviewTask.Status.APPROVED).exists():
        return False
    reqs = required_approvals(snippet)
    return requirements_met(reqs, _approved_set(snippet), SOURCE_LANGUAGE) and snippet.versions.filter(
        language=SOURCE_LANGUAGE, review_status__in=[ReviewStatus.APPROVED, ReviewStatus.PUBLISHED]
    ).exists()


@transaction.atomic
def publish(snippet) -> bool:
    if not can_publish(snippet):
        return False
    now = timezone.now()
    snippet.published_at = snippet.published_at or now
    snippet.verified_at = now
    snippet.review_status = ReviewStatus.PUBLISHED
    snippet.save(update_fields=["published_at", "verified_at", "review_status", "updated_at"])
    _release_corrections(snippet, now)
    # Reader questions this story answers (community posts show "Answered by the newsroom").
    snippet.contributions.filter(kind="question").update(status="answered")
    log(snippet, "published", payload={"verified_at": now.isoformat()})
    return True


@transaction.atomic
def reopen(snippet, reason) -> list[ReviewTask]:
    """Pull a snippet back into review with top priority (reports, expiry review, corrections)."""
    if reason not in ReviewTask.Reason.values:
        reason = ReviewTask.Reason.REPORT
    _active_tasks(snippet).update(active=False)
    snippet.review_status = ReviewStatus.REOPENED
    snippet.save(update_fields=["review_status", "updated_at"])
    tasks = _create_tasks(snippet, reason, priority=TOP_PRIORITY)
    log(snippet, "reopened", payload={"reason": reason, "tasks": [t.pk for t in tasks]})
    return tasks


def batch_approve(tasks, user) -> dict:
    """Approve many low-risk tasks at once (FR-3.7 Low tier); skips anything not batch-eligible."""
    done, skipped = [], []
    for task in tasks:
        if task.reason != ReviewTask.Reason.BATCH_LOW_RISK or task.snippet.risk_tier != RiskTier.LOW:
            skipped.append(task.pk)
            continue
        try:
            approve(task, user)
            done.append(task.pk)
        except (PermissionDenied, ValidationError):
            skipped.append(task.pk)
    return {"approved": done, "skipped": skipped}


def queue_for(user):
    """Review queue visible to `user`: tasks matching their roles; community_editor scoped to community."""
    qs = (ReviewTask.objects.filter(active=True)
          .exclude(status=ReviewTask.Status.OPEN, snippet__review_status__in=[ReviewStatus.REJECTED, ReviewStatus.EXPIRED])
          .select_related("snippet", "snippet__community"))
    if user.is_superuser or user.roles.filter(role="admin").exists():
        return qs
    q = Q(pk__in=[])
    for r in user.roles.all():
        # community_editor sees every task of their own community (can veto Sámi ones).
        cond = Q(required_role=r.role) if r.role != COMMUNITY_EDITOR else Q()
        if r.language:
            cond &= Q(language=r.language) | Q(language__isnull=True)
        if r.community_id or r.role == COMMUNITY_EDITOR:
            cond &= Q(snippet__community_id=r.community_id)
        q |= cond
    return qs.filter(q)


__all__ = [
    "enqueue", "required_approvals", "approve", "pending_checklist", "confirm_checklist", "reject", "request_changes",
    "can_publish", "publish", "reopen", "log", "batch_approve", "queue_for",
]
