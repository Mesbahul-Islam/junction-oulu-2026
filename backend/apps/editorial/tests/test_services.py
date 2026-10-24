"""Smoke tests of pure approval rules (FR-3.7, FR-3.9) — no DB."""

from django.test import override_settings

from apps.editorial import services as s
from apps.editorial.models import STANDARDS_CHECKLIST
from apps.editorial.services import Requirement as R


def test_high_needs_editor_and_language_reviewers():
    reqs = s.requirements_for("high", ["fi", "en", "ar"])
    assert reqs == [R("editor"), R("language_reviewer", "ar"), R("language_reviewer", "en")]


def test_every_translation_needs_its_own_language_reviewer_at_any_tier():
    assert s.requirements_for("medium", ["fi", "en"]) == [R("editor"), R("language_reviewer", "en")]
    assert s.requirements_for("low", ["fi", "uk", "ar"]) == [R("editor"), R("language_reviewer", "ar"), R("language_reviewer", "uk")]
    assert s.requirements_for("low", ["fi"]) == [R("editor")]


def test_sami_always_needs_language_reviewer():
    assert s.requirements_for("low", ["fi", "se"]) == [R("editor"), R("language_reviewer", "se")]
    high = s.requirements_for("high", ["fi", "smn"])
    assert high.count(R("language_reviewer", "smn")) == 1


@override_settings(AGENT_CONFIDENCE_THRESHOLD=0.7)
def test_escalation():
    assert s.effective_tier("low", 0.5, False) == "high"
    assert s.effective_tier("medium", 0.9, True) == "high"
    assert s.effective_tier("medium", 0.9, False) == "medium"


def test_requirements_met_is_per_language():
    reqs = s.requirements_for("high", ["fi", "en"])
    approved = {R("editor")}
    assert s.requirements_met(reqs, approved, "fi")
    assert not s.requirements_met(reqs, approved, "en")
    assert s.requirements_met(reqs, approved | {R("language_reviewer", "en")}, "en")


def test_standards_checklist():
    keys = dict(STANDARDS_CHECKLIST)
    assert {"fact_vs_opinion", "editorial_separated_from_ads", "sources_named"} <= set(keys)
    assert all("JSN" in label or key == "ai_role_disclosed" for key, label in STANDARDS_CHECKLIST)
