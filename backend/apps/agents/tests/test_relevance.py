"""The assignment agent picks stories by relevance to the community, never by risk tier."""

from apps.agents.graph.nodes.assignment import rank

OULU = {"name": "Oulu", "municipality": "Oulu"}


def _item(key, title, publisher=""):
    return {"key": key, "kind": "source", "title": title, "body": "", "publisher": publisher}


def test_local_story_beats_foreign_high_risk_story():
    ranked = rank(
        [_item("foreign", "Ranskassa poliisi tutkii, Migri muuttaa oleskelulupia"), _item("local", "Oulun bussilinja 3 muuttuu")],
        community=OULU,
    )
    assert [c["key"] for c in ranked] == ["local", "foreign"]


def test_audience_interests_raise_matching_topics():
    items = [_item("culture", "Teatteri avaa uuden näyttämön"), _item("sports", "Kärpät voitti ottelun")]
    assert rank(items, community=OULU, audience={"sports": 0.8})[0]["key"] == "sports"
    assert rank(items, community=OULU, audience={"culture": 0.8})[0]["key"] == "culture"


def test_local_feed_name_counts_as_local():
    ranked = rank([_item("a", "Kauppa sulkee ovensa"), _item("b", "Kauppa sulkee ovensa", publisher="Oulun seutu")], community=OULU)
    assert ranked[0]["key"] == "b"
