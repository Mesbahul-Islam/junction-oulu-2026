"""Model calls for the desks, made to survive small local models.

Every desk asks for a small JSON object as plain text and parses the answer leniently
(code fences, text around the object, trailing commas). A bad answer is retried once;
after that the desk gets ``(None, reason)`` and uses its fallback, so a run never stops
because a model misbehaved. The reason ends up in the story's review notes.
"""

from __future__ import annotations

import json
import re

from ..graph.llm import get_llm

_llms: dict = {}


def llm_for(desk: str):
    """The model for a desk (LLM_MODEL_<DESK> or the main one), created once per process."""
    if desk not in _llms:
        _llms[desk] = get_llm(desk)
    return _llms[desk]


def reset() -> None:
    """Pick up changed settings (start of every run)."""
    _llms.clear()


def model_name(desk: str) -> str:
    llm = llm_for(desk)
    return "" if llm.is_stub else getattr(llm, "spec", "")


def parse_json(raw: str):
    """The first JSON object in ``raw``, or None."""
    text = re.sub(r"```(?:json)?", "", raw or "")
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    chunk = text[start:end + 1]
    for candidate in (chunk, re.sub(r",\s*([}\]])", r"\1", chunk)):
        try:
            value = json.loads(candidate)
            return value if isinstance(value, dict) else None
        except ValueError:
            continue
    return None


def ask_json(desk: str, prompt: str, keys: list[str]) -> tuple[dict | None, str]:
    """Ask the desk's model for a JSON object with ``keys``. Returns (answer, problem)."""
    llm = llm_for(desk)
    if llm.is_stub:
        return None, "no AI model configured"
    shape = "{" + ", ".join(f'"{k}": ...' for k in keys) + "}"
    ask = f"{prompt}\n\nAnswer with only this JSON object and nothing else: {shape}"
    problem = ""
    for _ in range(2):
        try:
            raw = llm.text(ask)
        except Exception as exc:  # network, timeout, provider error
            return None, f"model call failed: {type(exc).__name__}: {str(exc)[:200]}"
        data = parse_json(raw)
        if data is not None and all(k in data for k in keys):
            return data, ""
        problem = "the model's answer wasn't the JSON asked for" if raw else "the model gave an empty answer"
        ask = f"{ask}\n\nYour last answer was not a valid JSON object with those keys. Reply with the JSON object only."
    return None, problem


def _content(message) -> str:
    content = message.content
    if isinstance(content, list):
        content = "".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    return re.sub(r"<think>.*?</think>", "", content or "", flags=re.S).strip()


def ask_json_with_tools(desk: str, prompt: str, keys: list[str], tools: list, max_steps: int = 4):
    """Like ``ask_json``, but the model may call ``tools`` (LangChain tools) first; each result
    is fed back until it answers with the JSON. Returns (answer, problem, calls), where
    ``calls`` lists the tool calls made: [{"tool", "args", "ok"}]."""
    from langchain_core.messages import HumanMessage, ToolMessage

    llm = llm_for(desk)
    if llm.is_stub:
        return None, "no AI model configured", []
    try:
        bound = llm.chat.bind_tools(tools)
    except Exception as exc:  # provider or model without tool calling
        return None, f"the model can't call tools ({type(exc).__name__})", []
    by_name = {t.name: t for t in tools}
    shape = "{" + ", ".join(f'"{k}": ...' for k in keys) + "}"
    messages = llm._messages(f"{prompt}\n\nWhen you have what you need, answer with only this JSON object: {shape}")
    calls: list[dict] = []
    for _ in range(max_steps):
        try:
            reply = bound.invoke(messages)
        except Exception as exc:
            return None, f"model call failed: {type(exc).__name__}: {str(exc)[:200]}", calls
        messages.append(reply)
        if getattr(reply, "tool_calls", None):
            for call in reply.tool_calls[:2]:
                tool = by_name.get(call["name"])
                result = tool.invoke(call["args"]) if tool else f"ERROR: there is no tool called {call['name']}"
                calls.append({"tool": call["name"], "args": call["args"], "ok": not str(result).startswith("ERROR")})
                messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
            continue
        data = parse_json(_content(reply))
        if data is not None and all(k in data for k in keys):
            return data, "", calls
        messages.append(HumanMessage(content=f"Reply with only the JSON object {shape}, nothing else."))
    return None, "no valid answer after reading the article", calls
