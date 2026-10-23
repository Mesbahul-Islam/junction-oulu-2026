"""LangGraph wiring of the AI newsroom (FR-3.2, FR-3.6).

    START -> scout -> assignment -> synthesizer -> explainer -> translator
          -> fact_checker -> standards -> tagging -> END

Every node is wrapped by ``_recorded`` which times it, appends a
``step_log`` entry to the state and - when ``state["run_id"]`` is set and the
run is not offline - writes an ``agents.AgentStep`` row. A node that raises
does not abort the run: the error is logged in ``state["errors"]`` and the
downstream agents work with whatever exists (and the fact-checker /
standards agents will fail anything incomplete, routing it to humans).

Newsroom role <-> human counterpart (FR-3.6):

=============  ===============================================
scout          community members / editors adding tips
assignment     news editor approving the daily plan
synthesizer    editor
explainer      editor
translator     native-language reviewer
fact_checker   editor resolving flags
standards      standards editor (final sign-off)
tagging        editor (metadata during review)
=============  ===============================================
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from .nodes.assignment import assignment
from .nodes.explainer import explainer
from .nodes.fact_checker import fact_checker
from .nodes.scout import scout
from .nodes.standards import standards
from .nodes.synthesizer import synthesizer
from .nodes.tagging import tagging
from .nodes.translator import translator
from .state import NewsroomState

logger = logging.getLogger(__name__)

PIPELINE: list[tuple[str, Callable[[NewsroomState], dict]]] = [
    ("scout", scout),
    ("assignment", assignment),
    ("synthesizer", synthesizer),
    ("explainer", explainer),
    ("translator", translator),
    ("fact_checker", fact_checker),
    ("standards", standards),
    ("tagging", tagging),
]


def json_safe(value: Any) -> Any:
    """Round-trip through JSON so the value can live in a JSONField."""
    from django.core.serializers.json import DjangoJSONEncoder

    return json.loads(json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False))


def _summarize(state: dict) -> dict:
    out: dict[str, Any] = {}
    for k, v in state.items():
        if isinstance(v, (list, dict)):
            out[k] = len(v)
        elif k in ("run_id", "community_id", "offline", "source_language", "language_targets"):
            out[k] = v
    return out


def _record_step(run_id: int, agent: str, state: dict, update: dict, duration_ms: int) -> None:
    from django.apps import apps

    AgentStep = apps.get_model("agents", "AgentStep")
    AgentStep.objects.create(
        run_id=run_id,
        agent=agent,
        input=json_safe(_summarize(state)),
        output=json_safe(update),
        duration_ms=duration_ms,
    )


def _recorded(agent: str, fn: Callable[[NewsroomState], dict]) -> Callable[[NewsroomState], dict]:
    def node(state: NewsroomState) -> dict:
        started = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        error = None
        try:
            update = fn(state) or {}
        except Exception as exc:
            logger.exception("Agent %s failed", agent)
            error = f"{type(exc).__name__}: {exc}"
            update = {"errors": list(state.get("errors") or []) + [{"agent": agent, "error": error[:1000]}]}
        duration_ms = int((time.perf_counter() - t0) * 1000)

        update["step_log"] = list(state.get("step_log") or []) + [{
            "agent": agent,
            "started_at": started.isoformat(),
            "duration_ms": duration_ms,
            "summary": _summarize(update),
            "error": error,
        }]
        if state.get("run_id") and not state.get("offline"):
            try:
                _record_step(state["run_id"], agent, state, update, duration_ms)
            except Exception:  # bookkeeping must never break the pipeline
                logger.exception("Could not record AgentStep for %s", agent)
        return update

    node.__name__ = agent
    return node


def build_graph():
    """Compile and return the newsroom ``StateGraph``. Use ``.invoke(state)``."""
    graph = StateGraph(NewsroomState)
    previous = START
    for name, fn in PIPELINE:
        graph.add_node(name, _recorded(name, fn))
        graph.add_edge(previous, name)
        previous = name
    graph.add_edge(previous, END)
    return graph.compile(name="newsroom")
