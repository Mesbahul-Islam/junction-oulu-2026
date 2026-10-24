"""Runs one newsroom shift.

    wire desk -> news editor (Jev + members' votes) -> for each picked story:
        reporter -> explainer -> translator -> fact-checker -> standards editor -> copy desk
    -> community vote (next shortlist) -> human editors (Ready to send / Needs review)

The run-level desks work on all articles at once; each picked story then goes through
its own small LangGraph. Every desk records where it is (``AgentRun.desk``,
``RunStory.stage``/``detail``) and what it did (``AgentStep``), which is what the
dashboard's live view shows. A story that breaks is marked failed; the others go on.
"""

from __future__ import annotations

import logging
import time
from typing import Any, TypedDict

from django.apps import apps
from django.utils import timezone
from langgraph.graph import END, START, StateGraph

from ..graph.text import LANGUAGE_LABELS
from ..models import AgentRun, AgentStep, RunStory
from . import ai, copy_desk, desks, news_editor, shortlist, wire

logger = logging.getLogger(__name__)


class StoryState(TypedDict, total=False):
    story_id: int
    source: dict
    languages: list[str]
    draft: dict
    explainer: dict
    translations: dict
    risk: str
    sensitive: list[str]
    issues: list[dict]
    snippet_id: int


# --- progress bookkeeping ----------------------------------------------------------------


def _at(run: AgentRun, desk: str, story: RunStory | None = None, detail: str = "") -> None:
    run.desk = desk
    run.save(update_fields=["desk", "updated_at"])
    if story is not None:
        story.stage, story.detail = desk, detail
        story.save(update_fields=["stage", "detail", "updated_at"])


def _log(run, desk, output: dict, started: float, story=None, snippet=None) -> None:
    AgentStep.objects.create(run=run, story=story, agent=desk, output=output, snippet=snippet,
                             duration_ms=int((time.perf_counter() - started) * 1000))


def target_languages(community) -> list[str]:
    """The community's languages plus every member's own language, in that order."""
    User = apps.get_model("accounts", "User")
    langs = list(community.languages or [])
    for lang in User.objects.filter(memberships__community=community).values_list("preferred_language", flat=True):
        if lang and lang not in langs:
            langs.append(lang)
    return langs


# --- the story graph ---------------------------------------------------------------------


def _desk(name: str, work):
    """Wrap a desk: mark the story as being there, run it, log it, collect its issues."""

    def node(state: StoryState) -> dict[str, Any]:
        story = RunStory.objects.select_related("run").get(pk=state["story_id"])
        _at(story.run, name, story)
        started = time.perf_counter()
        update = work(state, story) or {}
        new_issues = update.pop("issues", [])
        _log(story.run, name, {**{k: v for k, v in update.items() if k != "snippet"}, "issues": new_issues}, started,
             story=story, snippet=update.get("snippet"))
        update.pop("snippet", None)
        return {**update, "issues": list(state.get("issues") or []) + new_issues}

    node.__name__ = name
    return node


def _translate(state: StoryState, story: RunStory) -> dict:
    machine, sami = desks.translator_languages(state)
    out, issues = {}, []
    for n, lang in enumerate(machine, 1):
        _at(story.run, "translator", story, f"{LANGUAGE_LABELS.get(lang, lang)} ({n} of {len(machine)})")
        version, problem = desks.translate_one(state, lang)
        if version:
            out[lang] = version
        else:
            issues.append(desks.issue("translator", f"No {LANGUAGE_LABELS.get(lang, lang)} version: {problem}. "
                                                    "Those readers see English or Finnish.", False))
    if sami:
        issues.append(desks.issue("translator", "Sámi versions are written by a human translator, never by AI.", False))
    return {"translations": out, "issues": issues}


def _file(state: StoryState, story: RunStory) -> dict:
    snippet = copy_desk.file_story(story.run, story, state)
    story.snippet = snippet
    story.save(update_fields=["snippet", "updated_at"])
    return {"snippet_id": snippet.pk, "snippet": snippet}


def story_graph():
    g = StateGraph(StoryState)
    steps = [
        ("reporter", lambda s, _: desks.reporter(s)),
        ("explainer", lambda s, _: desks.explainer(s)),
        ("translator", _translate),
        ("fact_checker", lambda s, _: desks.fact_checker(s)),
        ("standards", lambda s, _: desks.standards(s)),
        ("copy_desk", _file),
    ]
    previous = START
    for name, work in steps:
        g.add_node(name, _desk(name, work))
        g.add_edge(previous, name)
        previous = name
    g.add_edge(previous, END)
    return g.compile(name="story")


# --- the shift ---------------------------------------------------------------------------


def run_newsroom(run: AgentRun) -> AgentRun:
    ai.reset()
    run.status, run.started_at, run.finished_at, run.error = AgentRun.Status.RUNNING, timezone.now(), None, ""
    run.save(update_fields=["status", "started_at", "finished_at", "error", "updated_at"])
    summary: dict[str, Any] = {}
    try:
        # Wire desk: fetch the Kaleva feeds.
        _at(run, "wire")
        started = time.perf_counter()
        fetched = wire.run_wire_desk(run.community)
        summary["wire"] = fetched["report"]
        _log(run, "wire", fetched["report"], started)

        # News editor: Jev ranks every candidate; the top ones become today's stories.
        _at(run, "news_editor")
        started = time.perf_counter()
        ranked = news_editor.rank(fetched["candidates"], run.community)
        picked = ranked[: run.max_stories]
        for n, pick in enumerate(picked, 1):
            RunStory.objects.create(run=run, rank=n, source_document=pick["doc"], title=pick["doc"].title[:500],
                                    jev_score=pick["score"], ranked_by=pick["ranked_by"], pick_reasons=pick["reasons"])
        summary["news_editor"] = {
            "considered": len(ranked), "picked": len(picked),
            "ranked_by": "jev" if any(p["ranked_by"] == "jev" for p in ranked) else "heuristic",
            "top": [{"title": p["doc"].title[:120], "score": p["score"], "jev": p["jev"], "votes": p["votes"],
                     "by": p["ranked_by"]} for p in ranked[:10]],
        }
        _log(run, "news_editor", summary["news_editor"], started)

        # Each story through the desks.
        languages = target_languages(run.community)
        graph = story_graph()
        for story in run.stories.select_related("source_document"):
            doc = story.source_document
            try:
                graph.invoke({
                    "story_id": story.pk, "languages": languages, "issues": [],
                    "source": {"title": doc.title, "body": doc.body, "url": doc.url, "publisher": doc.publisher},
                })
                story.stage, story.detail = RunStory.Stage.DONE, ""
            except Exception as exc:
                logger.exception("Story %s failed", story.pk)
                story.stage, story.error = RunStory.Stage.FAILED, f"{type(exc).__name__}: {exc}"[:2000]
            story.save(update_fields=["stage", "detail", "error", "updated_at"])

        # Community vote: post the next shortlist for members to vote on.
        _at(run, "community_vote")
        started = time.perf_counter()
        summary["community_vote"] = shortlist.publish(run, ranked, list(run.stories.all()), languages)
        _log(run, "community_vote", summary["community_vote"], started)

        stories = list(run.stories.select_related("snippet"))
        summary["result"] = {
            "ready": sum(1 for s in stories if s.snippet and s.snippet.review_level == "ready"),
            "needs_review": sum(1 for s in stories if s.snippet and s.snippet.review_level == "needs_review"),
            "failed": sum(1 for s in stories if s.stage == RunStory.Stage.FAILED),
            "languages": languages,
        }
        run.status = AgentRun.Status.SUCCEEDED
    except Exception as exc:
        logger.exception("Newsroom run %s failed", run.pk)
        run.status, run.error = AgentRun.Status.FAILED, f"{type(exc).__name__}: {exc}"[:5000]
    run.desk, run.state, run.finished_at = "", summary, timezone.now()
    run.save(update_fields=["status", "error", "desk", "state", "finished_at", "updated_at"])
    return run
