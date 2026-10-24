"""Model-agnostic LLM access for the newsroom agents.

Configure one model for all agents with three settings (in .env):

    LLM_PROVIDER=groq            # or gemini, openai, anthropic, mistral, ollama, openrouter ...
    LLM_MODEL=llama-3.3-70b-versatile
    LLM_API_KEY=gsk_...

``LLM_BASE_URL`` points ``LLM_PROVIDER=openai`` at any OpenAI-compatible server.
Optionally ``LLM_MODEL_<AGENT>=provider:model`` gives one agent a different model.
Models are created with LangChain's ``init_chat_model``, so every provider it
supports works once its ``langchain-<provider>`` package is installed.

``get_llm(agent)`` returns a ``ChatModelLLM`` or, when no model/key/package is
available, the deterministic ``StubLLM`` so the pipeline always runs (offline
demos, CI, tests). ``structured_call(prompt, schema, fallback=...)`` returns an
instance of the pydantic ``schema``; on any provider error it uses the node's
deterministic ``fallback`` and reports the error, so a flaky provider never kills
a run.

``python manage.py llm_check [--ping]`` shows (and tests) each agent's model.
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



AGENTS = ("assignment", "synthesizer", "explainer", "translator", "fact_checker")

# Friendly names -> LangChain provider ids.
PROVIDER_ALIASES = {
    "gemini": "google_genai", "google": "google_genai", "claude": "anthropic", "mistral": "mistralai",
    "grok": "xai", "openai_compatible": "openai", "openai-compatible": "openai",
}
# Bare model names (no provider given) are mapped by prefix.
_PREFIX_PROVIDERS = (
    ("gemini", "google_genai"), ("gpt-", "openai"), ("o1", "openai"), ("o3", "openai"), ("o4", "openai"),
    ("claude", "anthropic"), ("mistral", "mistralai"), ("deepseek", "deepseek"), ("grok", "xai"),
    ("qwen/", "groq"),  # Groq-hosted Qwen ids look like qwen/qwen3.8-27b
)
KEYLESS_PROVIDERS = {"ollama"}  # local models need no API key


def normalize_provider(name: str) -> str:
    name = (name or "").strip().lower()
    return PROVIDER_ALIASES.get(name, name)


def parse_model(spec: str, provider: str = "") -> tuple[str, str] | None:
    """(provider, model) from ``"provider:model"``, a bare model name, or an explicit provider.

    ``""``/``"stub"`` -> None. Raises ValueError when the provider can't be determined.
    """
    spec = (spec or "").strip()
    if not spec or spec.lower() == "stub":
        return None
    if provider:
        provider = normalize_provider(provider)
        prefix = provider + ":"  # tolerate LLM_MODEL=groq:llama-... alongside LLM_PROVIDER=groq
        return provider, spec[len(prefix):] if spec.lower().startswith(prefix) else spec
    if ":" in spec:
        prov, model = spec.split(":", 1)
        return normalize_provider(prov), model.strip()
    for prefix, prov in _PREFIX_PROVIDERS:
        if spec.lower().startswith(prefix):
            return prov, spec
    raise ValueError(f"Can't tell the provider of {spec!r}: set LLM_PROVIDER (e.g. groq, gemini, openai)")


def _provider_package(provider: str) -> str | None:
    """Top-level module LangChain needs for ``provider`` (None if LangChain doesn't know it)."""
    try:
        from langchain.chat_models.base import _BUILTIN_PROVIDERS

        entry = _BUILTIN_PROVIDERS.get(provider)
        return entry[0].split(".")[0] if entry else None
    except Exception:  # private registry moved: skip the check
        return provider


def resolve(agent: str | None = None) -> dict:
    """What ``get_llm(agent)`` would use.

    {agent, spec, provider, model, api_key, base_url, method, stub_reason}
    """
    import importlib.util

    from django.conf import settings

    main_provider = normalize_provider(getattr(settings, "LLM_PROVIDER", ""))
    override = (getattr(settings, "LLM_AGENT_MODELS", {}) or {}).get(agent or "", "")
    info = {"agent": agent or "default", "spec": "stub", "provider": "", "model": "", "api_key": "",
            "base_url": "", "method": "", "stub_reason": ""}
    try:
        parsed = parse_model(override) if override else parse_model(getattr(settings, "LLM_MODEL", ""), main_provider)
    except ValueError as exc:
        info["stub_reason"] = str(exc)
        return info
    if parsed is None:
        info["stub_reason"] = "no model set (LLM_MODEL is empty or 'stub')"
        return info

    provider, model = parsed
    is_main = provider == main_provider or (not main_provider and not override)
    keys = getattr(settings, "LLM_API_KEYS", {}) or {}
    api_key = (getattr(settings, "LLM_API_KEY", "") if is_main else "") or keys.get(provider, "")
    base_url = getattr(settings, "LLM_BASE_URL", "") if is_main else ""
    method = getattr(settings, "LLM_STRUCTURED_OUTPUT", "auto") or "auto"
    if method == "auto":
        method = "json_schema"  # native JSON-schema output; ChatModelLLM retries with tool calling if refused
    info.update(spec=f"{provider}:{model}", provider=provider, model=model, api_key=api_key, base_url=base_url, method=method)

    package = _provider_package(provider)
    if package is None:
        info["stub_reason"] = f"unknown provider {provider!r}"
    elif importlib.util.find_spec(package) is None:
        info["stub_reason"] = f"package for {provider!r} not installed: add langchain-{provider.replace('_', '-')} to requirements.txt"
    elif not api_key and provider not in KEYLESS_PROVIDERS and not base_url:
        info["stub_reason"] = "no API key (set LLM_API_KEY)" if is_main else f"no API key for {provider}"
    return info


class ChatModelLLM:
    """Any LangChain chat model, created with ``init_chat_model``."""

    is_stub = False

    def __init__(self, provider: str, model: str, api_key: str = "", base_url: str = "", method: str = "json_schema"):
        from django.conf import settings
        from langchain.chat_models import init_chat_model

        max_out = int(getattr(settings, "LLM_MAX_OUTPUT_TOKENS", 0) or 0)
        if provider == "ollama":
            # Local server: no key. Address from LLM_BASE_URL, else OLLAMA_HOST (set in docker-compose).
            kwargs: dict[str, Any] = {"temperature": 0, "client_kwargs": {"timeout": 300}}
            if base_url:
                kwargs["base_url"] = base_url
            if max_out:
                kwargs["num_predict"] = max_out
        else:
            kwargs = {"temperature": 0, "timeout": 90, "max_retries": int(getattr(settings, "LLM_MAX_RETRIES", 2))}
            if max_out:
                kwargs["max_tokens"] = max_out
            if api_key or base_url:
                kwargs["api_key"] = api_key or "not-needed"  # local OpenAI-compatible servers ignore it
            if base_url:
                kwargs["base_url"] = base_url
        self.provider, self.model_name, self.method = provider, model, method
        self.spec = f"{provider}:{model}"
        self.chat = init_chat_model(model, model_provider=provider, **kwargs)

    def _messages(self, prompt: str):
        from langchain_core.messages import HumanMessage, SystemMessage

        return [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]

    def structured(self, prompt: str, schema: type[T], fallback: Callable[[], T | dict] | None = None) -> T:
        try:
            return self._structured(prompt, schema, self.method)
        except Exception as exc:
            # A model that rejects one structured-output mode (HTTP 400, e.g. no JSON-schema support
            # or a malformed tool call) often handles the other. Rate limits and outages are re-raised.
            other = "function_calling" if self.method == "json_schema" else "json_schema"
            if _status(exc) != 400:
                raise
            logger.info("%s rejected %s (%s); retrying with %s", self.spec, self.method, str(exc)[:120], other)
            return self._structured(prompt, schema, other)

    def _structured(self, prompt: str, schema: type[T], method: str) -> T:
        runnable = self.chat.with_structured_output(schema, method=method)
        result = runnable.invoke(self._messages(prompt))
        if isinstance(result, dict):
            result = schema.model_validate(result)
        return result



def match_languages(entries: list, langs: list[str], agent: str, errors: list) -> dict:
    """File a model's per-language answers under the languages that were *requested*.

    With one requested language, the answer is that language whatever the model
    labelled it. With several, only labels that were requested count and the first
    entry per language wins; duplicates and unknown labels are reported, not stored.
    Missing languages are simply absent (the caller falls back).
    """
    if len(langs) == 1:
        return {langs[0]: entries[0]} if entries else {}
    filed: dict = {}
    for entry in entries:
        label = (getattr(entry, "language", "") or "").strip().lower()
        if label not in langs:
            errors.append({"agent": agent, "error": f"answer labelled {label!r} wasn't requested; ignored"})
        elif label in filed:
            errors.append({"agent": agent, "error": f"two answers labelled {label!r}; kept the first"})
        else:
            filed[label] = entry
    return filed


def language_chunks(langs: list[str]) -> list[list[str]]:
    """Split target languages into groups of LLM_LANGUAGES_PER_CALL (default 1; 0 = one group)."""
    from django.conf import settings

    size = int(getattr(settings, "LLM_LANGUAGES_PER_CALL", 1)) or len(langs) or 1
    return [langs[i:i + size] for i in range(0, len(langs), size)]


def _status(exc: Exception) -> int | None:
    """HTTP status of a provider SDK error, if it has one."""
    for attr in ("status_code", "code", "status"):
        value = getattr(exc, attr, None) or getattr(getattr(exc, "response", None), attr, None)
        if isinstance(value, int):
            return value
    return None


_cache: dict[tuple, Any] = {}


def get_llm(agent: str | None = None, force_stub: bool = False):
    """The LLM for ``agent`` (cached per model/key). Falls back to ``StubLLM``."""
    if force_stub:
        return StubLLM()
    info = resolve(agent)
    if info["stub_reason"]:
        return StubLLM()
    cache_key = (info["provider"], info["model"], info["api_key"], info["base_url"], info["method"])
    if cache_key not in _cache:
        try:
            _cache[cache_key] = ChatModelLLM(info["provider"], info["model"], info["api_key"], info["base_url"], info["method"])
        except Exception:  # bad config the checks above didn't catch
            logger.exception("Could not initialise %s; using StubLLM", info["spec"])
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
    llm = llm or get_llm(agent)
    try:
        return llm.structured(prompt, schema, fallback)
    except Exception as exc:  # network, rate limit, validation...
        logger.warning("structured_call failed (%s, %s): %s", agent or schema.__name__, getattr(llm, "spec", "?"), exc)
        if errors is not None:
            errors.append({"agent": agent, "error": f"LLM failure, used fallback: {exc}"[:500]})
        if fallback is not None:
            value = fallback()
            return value if isinstance(value, schema) else schema.model_validate(value)
        return _empty_instance(schema)


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
