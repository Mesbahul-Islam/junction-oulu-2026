"""Model-agnostic LLM configuration: LLM_PROVIDER + LLM_MODEL + LLM_API_KEY, optional per-agent overrides."""

import pytest

from apps.agents.graph import llm


@pytest.fixture(autouse=True)
def clean(settings):
    llm._cache.clear()
    settings.LLM_PROVIDER = "groq"
    settings.LLM_MODEL = "llama-3.3-70b-versatile"
    settings.LLM_API_KEY = "gsk-test"
    settings.LLM_BASE_URL = ""
    settings.LLM_STRUCTURED_OUTPUT = "auto"
    settings.LLM_AGENT_MODELS = {a: "" for a in llm.AGENTS}
    settings.LLM_API_KEYS = {"anthropic": "a-key", "openai": ""}


def test_three_settings_pick_provider_model_and_key():
    client = llm.get_llm("synthesizer")
    assert type(client.chat).__name__ == "ChatGroq"
    assert client.spec == "groq:llama-3.3-70b-versatile"
    assert client.method == "json_schema"  # auto: native JSON schema, tool calling as retry


@pytest.mark.parametrize("alias,cls", [("gemini", "ChatGoogleGenerativeAI"), ("google", "ChatGoogleGenerativeAI"),
                                       ("claude", "ChatAnthropic"), ("openai", "ChatOpenAI")])
def test_friendly_provider_names(settings, alias, cls):
    settings.LLM_PROVIDER = alias
    settings.LLM_MODEL = "some-model"
    client = llm.get_llm("assignment")
    assert type(client.chat).__name__ == cls and client.method == "json_schema"


def test_missing_key_or_model_falls_back_to_stub(settings):
    settings.LLM_API_KEY = ""
    assert llm.resolve("assignment")["stub_reason"] == "no API key (set LLM_API_KEY)"
    assert llm.get_llm("assignment").is_stub
    settings.LLM_MODEL = ""
    assert llm.get_llm("assignment").is_stub


def test_unknown_provider_and_missing_package(settings):
    settings.LLM_PROVIDER = "nope"
    assert "unknown provider" in llm.resolve()["stub_reason"]
    settings.LLM_PROVIDER = "mistral"  # langchain-mistralai isn't installed
    assert "not installed" in llm.resolve()["stub_reason"]


def test_ollama_needs_no_key_and_uses_base_url(settings):
    settings.LLM_PROVIDER, settings.LLM_MODEL, settings.LLM_API_KEY = "ollama", "qwen3:8b", ""
    settings.LLM_MAX_OUTPUT_TOKENS = 900
    assert llm.resolve()["stub_reason"] == ""
    chat = llm.get_llm("translator").chat
    assert type(chat).__name__ == "ChatOllama" and chat.base_url is None and chat.num_predict == 900  # OLLAMA_HOST decides
    llm._cache.clear()
    settings.LLM_BASE_URL = "http://host.docker.internal:11434"
    assert llm.get_llm("translator").chat.base_url == "http://host.docker.internal:11434"


def test_per_agent_override_uses_its_own_provider_key(settings):
    settings.LLM_AGENT_MODELS["translator"] = "anthropic:claude-haiku-5-5"
    assert type(llm.get_llm("translator").chat).__name__ == "ChatAnthropic"
    assert type(llm.get_llm("explainer").chat).__name__ == "ChatGroq"
    settings.LLM_AGENT_MODELS["fact_checker"] = "openai:gpt-5.5-mini"
    assert llm.resolve("fact_checker")["stub_reason"] == "no API key for openai"


def test_openai_compatible_server_needs_no_key(settings):
    settings.LLM_PROVIDER, settings.LLM_MODEL, settings.LLM_API_KEY = "openai", "llama3.3", ""
    settings.LLM_BASE_URL = "http://localhost:8001/v1"
    client = llm.get_llm("assignment")
    assert client.chat.openai_api_base == "http://localhost:8001/v1"


def test_legacy_provider_prefix_and_bare_names(settings):
    settings.LLM_PROVIDER = ""
    settings.LLM_MODEL = "groq:llama-3.3-70b-versatile"
    assert llm.resolve()["spec"] == "groq:llama-3.3-70b-versatile"
    assert llm.parse_model("gemini-3.1-flash-lite") == ("google_genai", "gemini-3.1-flash-lite")
    assert llm.parse_model("llama-3.3", "groq") == ("groq", "llama-3.3")
    assert llm.parse_model("groq:llama-3.3", "groq") == ("groq", "llama-3.3")
    assert llm.parse_model("Qwen/Qwen3.8-27B") == ("groq", "Qwen/Qwen3.8-27B")


def test_qwen_ids_map_to_groq():
    assert llm.parse_model("qwen/qwen3.8-27b") == ("groq", "qwen/qwen3.8-27b")
    assert llm.parse_model("Qwen/Qwen3.8-27B") == ("groq", "Qwen/Qwen3.8-27B")


def test_structured_retries_other_mode_on_400_but_not_on_429(monkeypatch):
    from apps.agents.graph.schemas import AssignmentProposal

    client = llm.get_llm("assignment")
    calls = []

    class Err(Exception):
        def __init__(self, status):
            self.status_code = status

    def fake(prompt, schema, method):
        calls.append(method)
        if method == "json_schema":
            raise Err(400)
        return AssignmentProposal(reader_needs=["information"], risk_tier="low")

    monkeypatch.setattr(client, "_structured", fake)
    assert client.structured("p", AssignmentProposal).risk_tier == "low"
    assert calls == ["json_schema", "function_calling"]

    monkeypatch.setattr(client, "_structured", lambda *a: (_ for _ in ()).throw(Err(429)))
    with pytest.raises(Err):
        client.structured("p", AssignmentProposal)


def test_language_chunks(settings):
    settings.LLM_LANGUAGES_PER_CALL = 0
    assert llm.language_chunks(["en", "sv", "uk"]) == [["en", "sv", "uk"]]
    settings.LLM_LANGUAGES_PER_CALL = 2
    assert llm.language_chunks(["en", "sv", "uk"]) == [["en", "sv"], ["uk"]]


def test_output_cap_and_retries_reach_the_model(settings):
    settings.LLM_MAX_OUTPUT_TOKENS, settings.LLM_MAX_RETRIES = 900, 6
    chat = llm.get_llm("assignment").chat
    assert chat.max_tokens == 900 and chat.max_retries == 6
