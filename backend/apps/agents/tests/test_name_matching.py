"""Fact-checker name checks tolerate Finnish inflection but still catch wrong names."""

import pytest

from apps.agents.graph.nodes.fact_checker import check_draft_against_source, compare_facts, extract_facts
from apps.agents.graph.text import name_matches


@pytest.mark.parametrize("name,word", [
    ("Oulussa", "Oulu"), ("Raksilassa", "Raksila"), ("Oulun", "Oulu"), ("Kärpille", "Kärpät"),
    ("Kärpät", "Kärpille"), ("Tampere", "Tampereella"), ("Karjalainen", "Karjalaisen"), ("TPS", "TPSn"),
])
def test_inflected_forms_match(name, word):
    assert name_matches(name, [word])


@pytest.mark.parametrize("name,word", [
    ("Raksilassa", "Raskala"), ("Oulu", "Oulunsalo"), ("Oulussa", "Oulunsalo"), ("Kemi", "Kempele"),
    ("Petri", "Peter"), ("HIFK", "HPK"), ("Kärpät", "Tappara"),
])
def test_different_names_dont_match(name, word):
    assert not name_matches(name, [word])


def test_translation_keeps_inflected_place_names():
    draft = extract_facts("Kärpät ja KalPa kohtaavat Raksilassa. Ottelu pelataan Oulussa.")
    good = extract_facts("Kärpät and KalPa meet at Raksila. The game is played in Oulu.")
    bad = extract_facts("Kärpät and KalPa meet in Raskala. The game is played in Oulu.")
    assert compare_facts(draft, good, language="en", check_names=True) == []
    missing = [m["value"] for m in compare_facts(draft, bad, language="en", check_names=True)]
    assert missing == ["Raksilassa"]


def test_draft_names_found_in_source_despite_inflection():
    draft = {"language": "fi", "headline": "Oulun Kärpille sakko", "summary": "Liiga sakotti Kärpille.", "key_facts": []}
    assert check_draft_against_source(draft, "Liiga on sakottanut Oulun Kärpät -seuraa.") == []
