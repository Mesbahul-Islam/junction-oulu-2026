"""Smoke test: run the full LangGraph newsroom offline with the StubLLM.

No database, no network: ``offline=True`` makes the scout pass through the
in-memory items and the step wrapper skips AgentStep rows.
"""

import pytest

from apps.agents.graph.build import PIPELINE, build_graph
from apps.agents.graph.llm import StubLLM, get_llm
from apps.agents.graph.nodes.fact_checker import compare_facts, extract_facts


@pytest.fixture(autouse=True)
def _force_stub(settings):
    settings.ANTHROPIC_API_KEY = ""
    settings.AGENT_CONFIDENCE_THRESHOLD = 0.7


def _state():
    return {
        "offline": True,
        "community_id": None,
        "community": {
            "id": 1, "name": "Oulu newcomers", "slug": "oulu", "municipality": "Oulu",
            "bbox": [25.3, 64.9, 25.7, 65.1], "languages": ["fi", "en", "se", "ar"],
        },
        "glossary": [{"language": "en", "term_fi": "Migri", "term": "Migri (Finnish Immigration Service)", "note": ""}],
        "context_entries": [
            {"id": 11, "language": "fi", "topic": "immigration", "body": "Migri käsittelee oleskelulupahakemukset."},
        ],
        "raw_items": [
            {
                "key": "mem:1", "kind": "source", "source_document_id": None, "url": "https://migri.fi/x",
                "title": "Oleskelulupien käsittely muuttuu Oulussa",
                "body": "Migri avaa uuden palvelupisteen Ouluun 1.12.2026. Palvelupiste on auki klo 9.00-16.00. "
                        "Ajanvaraus on pakollinen ja käsittelyaika lyhenee 30 päivään.",
                "publisher": "Migri", "version": 1, "content_hash": "h1", "fetched_at": "",
            },
            {
                "key": "signal:7", "kind": "community_signal", "contribution_id": 7, "url": "",
                "title": "Missä voi uida talvella?", "body": "Missä voi uida talvella? Onko uimahalli auki?",
                "publisher": "community", "version": 0, "contribution_kind": "question", "occurrence_count": 3,
            },
        ],
        "errors": [],
        "step_log": [],
    }


def test_stub_llm_selected_without_api_key():
    assert isinstance(get_llm(), StubLLM)


def test_graph_runs_offline_end_to_end():
    final = build_graph().invoke(_state())

    assert [s["agent"] for s in final["step_log"]] == [name for name, _ in PIPELINE]
    assert not [s for s in final["step_log"] if s["error"]], final["errors"]
    assert final["language_targets"] == ["en", "se", "ar"]

    a = final["assignments"]["mem:1"]
    assert a["risk_tier"] == "high" and a["reader_needs"] and a["expires_at"]

    draft = final["drafts"]["mem:1"]
    assert draft["headline"] and draft["key_facts"]
    assert set(draft["explainer"]) == {"newcomer", "seasonal_worker", "student", "resident"}
    assert draft["background"] == "Migri käsittelee oleskelulupahakemukset."  # only from the context library
    assert draft["background_context_ids"] == [11]

    tr = final["translations"]["mem:1"]
    assert tr["se"]["needs_human_translation"] and tr["se"]["summary"] == ""  # FR-3.9: no Sámi MT
    assert tr["en"]["is_machine_translated"] and "Finnish Immigration Service" in tr["en"]["summary"]

    ver = final["verification"]["mem:1"]
    assert "se" not in ver and ver["fi"]["passed"] and ver["en"]["passed"], ver
    assert final["confidence"]["mem:1"] >= 0.7

    # Community tip without an official source is flagged for verification.
    assert final["verification"]["signal:7"]["fi"]["passed"] is False
    assert final["standards"]["mem:1"]["results"]
    t = final["tags"]["mem:1"]
    assert "immigration" in t["tags"] and len(t["embedding"]) == 64 and t["geo_bbox"] == [25.3, 64.9, 25.7, 65.1]


def test_fact_compare_detects_changed_number():
    ref = extract_facts("Käsittelyaika on 30 päivää 1.12.2026 alkaen klo 9.00.")
    bad = extract_facts("Processing takes 20 days from 1.12.2026 at 9:00.")
    kinds = {(m["kind"], m["value"]) for m in compare_facts(ref, bad, language="en", check_names=False)}
    assert ("number", "30") in kinds and ("number", "20") in kinds
    assert not any(k == "date" or k == "time" for k, _ in kinds)
