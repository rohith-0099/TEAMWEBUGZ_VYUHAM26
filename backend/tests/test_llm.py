from types import SimpleNamespace

import litellm
import pytest
from pydantic import BaseModel

from app import llm
from app.config import settings


class Out(BaseModel):
    answer: str
    score: float


def reply(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                           usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2))


@pytest.fixture
def provider(monkeypatch, llm_on):
    """Scripted provider: each call consumes one reply, or raises it if it's an exception."""
    calls = []
    script = []

    async def acompletion(**kwargs):
        calls.append(kwargs)
        item = script.pop(0)
        if isinstance(item, Exception):
            raise item
        return reply(item)

    monkeypatch.setattr(litellm, "acompletion", acompletion)
    store = {}
    monkeypatch.setattr(llm, "_cache_get", store.get)
    monkeypatch.setattr(llm, "_cache_put", store.__setitem__)
    monkeypatch.setattr(llm, "RATE_LIMIT_BACKOFF_S", (0, 0))
    return SimpleNamespace(calls=calls, script=script, cache=store)


async def test_mock_mode_returns_valid_instance(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    assert isinstance(await llm.complete_json("s", "u", Out), Out)


async def test_parses_fenced_json_and_uses_settings(provider):
    provider.script.append('```json\n{"answer": "a", "score": 0.5}\n```')
    result = await llm.complete_json("sys", "usr", Out, model="verify")
    assert result == Out(answer="a", score=0.5)
    call = provider.calls[0]
    assert call["model"] == "test/verify" and call["temperature"] == 0
    assert "JSON Schema" in call["messages"][0]["content"]


async def test_invalid_output_retries_once_with_the_error(provider):
    provider.script += ["not json", '{"answer": "a", "score": 1}']
    assert (await llm.complete_json("s", "u", Out)).answer == "a"
    assert "previous output was invalid" in provider.calls[1]["messages"][1]["content"]


async def test_invalid_twice_raises_llm_error(provider):
    provider.script += ["nope", '{"answer": "missing score"}']
    with pytest.raises(llm.LLMError):
        await llm.complete_json("s", "u", Out)
    assert len(provider.calls) == 2


async def test_rate_limit_backs_off_then_succeeds(provider):
    limited = litellm.RateLimitError("slow down", llm_provider="test", model="m")
    provider.script += [limited, limited, '{"answer": "a", "score": 1}']
    assert (await llm.complete_json("s", "u", Out)).answer == "a"
    assert len(provider.calls) == 3


async def test_rate_limit_gives_up_with_llm_error(provider):
    limited = litellm.RateLimitError("slow down", llm_provider="test", model="m")
    provider.script += [limited, limited, limited]
    with pytest.raises(llm.LLMError):
        await llm.complete_json("s", "u", Out)


async def test_provider_failure_becomes_llm_error(provider):
    provider.script.append(litellm.APIConnectionError(message="down", llm_provider="test", model="m"))
    with pytest.raises(llm.LLMError):
        await llm.complete_json("s", "u", Out)


async def test_second_identical_call_comes_from_cache(provider):
    provider.script.append('{"answer": "a", "score": 1}')
    usage = llm.begin_usage()
    first = await llm.complete_json("s", "u", Out)
    second = await llm.complete_json("s", "u", Out)
    assert first == second and len(provider.calls) == 1
    assert usage.calls == 1 and usage.cached == 1 and usage.prompt_tokens == 3


async def test_cache_can_be_disabled(provider):
    provider.script += ['{"answer": "a", "score": 1}', '{"answer": "b", "score": 1}']
    await llm.complete_json("s", "u", Out, cache=False)
    assert (await llm.complete_json("s", "u", Out, cache=False)).answer == "b"


async def test_missing_model_name_is_a_clear_error(provider, monkeypatch):
    monkeypatch.setattr(settings, "llm_extract_model", "")
    with pytest.raises(llm.LLMError, match="LLM_EXTRACT_MODEL"):
        await llm.complete_json("s", "u", Out)


async def test_complete_text_returns_raw_content(provider):
    provider.script.append("plain words")
    assert await llm.complete_text("s", "u") == "plain words"
