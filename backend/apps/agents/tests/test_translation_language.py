"""Translations: one language per call, filed by the requested language, and language-checked."""

from types import SimpleNamespace

import pytest

from apps.agents.graph.llm import language_chunks, match_languages
from apps.agents.graph.nodes.fact_checker import check_language, fact_checker
from apps.agents.graph.text import language_problem

FI = "Liiga on langettanut Oulun Kärpille sakkorangaistuksen. Sakko koskee päävalmentaja Petri Karjalaista ja hänen viikonlopun ulostuloaan."
EN = "The Liiga has fined Oulun Kärpät. The fine concerns head coach Petri Karjalainen and his comments at the weekend."
SV = "Liiga har gett Oulun Kärpät böter. Böterna gäller huvudtränaren Petri Karjalainen och hans uttalanden i helgen."
UK = "Ліга оштрафувала Оулун Кярпят. Штраф стосується головного тренера Петрі Карьялайнена та його заяв на вихідних."
RU = "Лига наложила штраф на Оулун Кярпят. Штраф касается главного тренера Петри Карьялайнена и его заявлений на выходных."
AR = "فرضت الدوري غرامة على أولو كاربات. تتعلق الغرامة بالمدرب الرئيسي بيتري كاريالاينن وتصريحاته في نهاية الأسبوع."


def test_one_language_per_call_by_default(settings):
    del settings.LLM_LANGUAGES_PER_CALL
    assert language_chunks(["en", "sv", "uk"]) == [["en"], ["sv"], ["uk"]]
    settings.LLM_LANGUAGES_PER_CALL = 0
    assert language_chunks(["en", "sv", "uk"]) == [["en", "sv", "uk"]]


def test_single_request_is_filed_under_requested_language_whatever_the_label():
    entry = SimpleNamespace(language="sv", headline="...")
    assert match_languages([entry], ["en"], "translator", []) == {"en": entry}


def test_multi_request_ignores_duplicates_and_unrequested_labels():
    a, b, c = (SimpleNamespace(language=lang) for lang in ("sv", "sv", "de"))
    errors = []
    assert match_languages([a, b, c], ["en", "sv"], "translator", errors) == {"sv": a}
    assert len(errors) == 2


@pytest.mark.parametrize("text,lang", [(EN, "en"), (SV, "sv"), (UK, "uk"), (RU, "ru"), (AR, "ar"), (FI, "fi")])
def test_correct_language_passes(text, lang):
    assert language_problem(text, lang) is None


@pytest.mark.parametrize("text,lang,expect", [
    (SV, "en", "Swedish"), (RU, "uk", "Russian"), (UK, "ru", "Ukrainian"),
    (RU, "sv", "cyrillic"), (SV, "ar", "latin"), (EN, "sv", "English"),
])
def test_wrong_language_is_caught(text, lang, expect):
    assert expect in language_problem(text, lang)


def test_untranslated_finnish_and_offline_stub():
    assert "Finnish original" in check_language(FI, "sv", FI)[0]["issue"]
    assert check_language(f"[sv] {FI}", "sv", FI) == []  # offline stub text isn't judged


def test_fact_checker_fails_a_mislabelled_translation(settings):
    settings.LLM_MODEL = "stub"
    draft = {"language": "fi", "headline": "Sakko Kärpille", "summary": FI, "key_facts": [], "explainer": {}}
    state = {
        "raw_items": [{"key": "k", "title": "Sakko Kärpille", "body": FI}],
        "drafts": {"k": draft},
        "translations": {"k": {
            "en": {"headline": "Fine", "summary": SV, "key_facts": [], "explainer": {}},  # Swedish filed as English
            "uk": {"headline": "Штраф", "summary": UK, "key_facts": [], "explainer": {}},
        }},
    }
    out = fact_checker(state)["verification"]["k"]
    assert not out["en"]["passed"] and any(m["kind"] == "language" for m in out["en"]["mismatches"])
    assert not any(m["kind"] == "language" for m in out["uk"]["mismatches"])
