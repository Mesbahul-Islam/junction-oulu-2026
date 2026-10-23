"""Provider-agnostic LLM access for the newsroom agents.

* ``get_llm()`` returns a LangChain ``ChatGoogleGenerativeAI`` (Gemini Flash, model
  ``settings.LLM_MODEL``) when ``settings.GEMINI_API_KEY`` is set, otherwise a deterministic
  ``StubLLM`` so the whole pipeline runs offline (demos, CI, tests).
* ``structured_call(prompt, schema, fallback=...)`` returns an instance of the
  pydantic ``schema``. Every node passes a deterministic ``fallback`` callable;
  the stub uses it directly and the real LLM falls back to it on any error, so
  a flaky provider never kills a run (the error is reported back to the caller).

Swapping providers: implement another branch in ``get_llm()`` returning any
LangChain chat model that supports ``with_structured_output``.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

SYSTEM_PROMPT = (
    "You are part of a local-news newsroom pipeline in Finland. "
    "Be factual and neutral. Never invent facts, numbers, dates, names or quotes "
    "that are not in the provided material. Keep dates in numeric dd.mm.yyyy form "
    "and keep all numbers exactly as written in the source."
)


class StubLLM:
    """Deterministic offline stand-in. It never "thinks": it either runs the
    node-supplied fallback or builds an empty-ish instance of the schema."""

    is_stub = True
    model_name = "stub"

    def structured(self, prompt: str, schema: type[T], fallback: Callable[[], T | dict] | None = None) -> T:
        if fallback is not None:
            value = fallback()
            return value if isinstance(value, schema) else schema.model_validate(value)
        return _empty_instance(schema)

    def text(self, prompt: str, fallback: Callable[[], str] | None = None) -> str:
        return fallback() if fallback else ""


class GeminiLLM:
    """Thin wrapper over ``langchain_google_genai.ChatGoogleGenerativeAI`` (Gemini Flash)."""

    is_stub = False

    def __init__(self, api_key: str, model: str):
        from langchain_google_genai import ChatGoogleGenerativeAI

        self.model_name = model
        self.chat = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0,
            max_output_tokens=4096,
            timeout=90,
            max_retries=2,
        )

    def _messages(self, prompt: str):
        from langchain_core.messages import HumanMessage, SystemMessage

        return [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]

    def structured(self, prompt: str, schema: type[T], fallback: Callable[[], T | dict] | None = None) -> T:
        # json_schema = Gemini's native structured output (response schema), no tool-call parsing
        runnable = self.chat.with_structured_output(schema, method="json_schema")
        result = runnable.invoke(self._messages(prompt))
        if isinstance(result, dict):
            result = schema.model_validate(result)
        return result

    def text(self, prompt: str, fallback: Callable[[], str] | None = None) -> str:
        msg = self.chat.invoke(self._messages(prompt))
        content = msg.content
        if isinstance(content, list):  # content blocks
            content = "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
        return str(content)


_cache: dict[tuple[str, str], Any] = {}


def get_llm(force_stub: bool = False):
    """Return the configured LLM client (cached per api-key/model)."""
    from django.conf import settings

    api_key = getattr(settings, "GEMINI_API_KEY", "") or ""
    model = getattr(settings, "LLM_MODEL", "gemini-3.8-flash")
    if force_stub or not api_key:
        return StubLLM()
    cache_key = (api_key, model)
    if cache_key not in _cache:
        try:
            _cache[cache_key] = GeminiLLM(api_key, model)
        except Exception:  # pragma: no cover - import/config problems
            logger.exception("Could not initialise ChatGoogleGenerativeAI; using StubLLM")
            return StubLLM()
    return _cache[cache_key]


def structured_call(
    prompt: str,
    schema: type[T],
    fallback: Callable[[], T | dict] | None = None,
    *,
    llm=None,
    errors: list | None = None,
    agent: str = "",
) -> T:
    """Ask the LLM for JSON matching ``schema`` (a pydantic model).

    On provider failure the deterministic ``fallback`` is used and an entry is
    appended to ``errors`` (if given) so the run log shows the degradation.
    """
    llm = llm or get_llm()
    try:
        return llm.structured(prompt, schema, fallback)
    except Exception as exc:  # network, rate limit, validation...
        logger.warning("structured_call failed (%s): %s", agent or schema.__name__, exc)
        if errors is not None:
            errors.append({"agent": agent, "error": f"LLM failure, used fallback: {exc}"[:500]})
        if fallback is not None:
            value = fallback()
            return value if isinstance(value, schema) else schema.model_validate(value)
        return _empty_instance(schema)


def text_call(prompt: str, fallback: Callable[[], str] | None = None, *, llm=None, errors=None, agent="") -> str:
    llm = llm or get_llm()
    try:
        return llm.text(prompt, fallback)
    except Exception as exc:
        logger.warning("text_call failed (%s): %s", agent, exc)
        if errors is not None:
            errors.append({"agent": agent, "error": f"LLM failure, used fallback: {exc}"[:500]})
        return fallback() if fallback else ""


def is_stub(llm=None) -> bool:
    return bool(getattr(llm or get_llm(), "is_stub", False))


def _empty_instance(schema: type[T]) -> T:
    data: dict[str, Any] = {}
    for name, field in schema.model_fields.items():
        if not field.is_required():
            continue
        ann = field.annotation
        origin = getattr(ann, "__origin__", None)
        if ann is str:
            data[name] = ""
        elif ann in (int, float):
            data[name] = 0
        elif ann is bool:
            data[name] = False
        elif origin is list or ann is list:
            data[name] = []
        elif origin is dict or ann is dict:
            data[name] = {}
        else:
            data[name] = None
    return schema.model_validate(data)
