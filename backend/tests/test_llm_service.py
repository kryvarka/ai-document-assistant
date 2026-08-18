from unittest.mock import AsyncMock, MagicMock

import pytest

from src.middleware.error_handler import LLMServiceError
from src.services.llm_service import LLMService


@pytest.fixture
def service(monkeypatch):
    instance = LLMService()
    monkeypatch.setattr(LLMService, "_backoff", AsyncMock())
    return instance


def _client_raising(*errors, final_text: str | None = None):
    responses: list = list(errors)
    if final_text is not None:
        responses.append(MagicMock(text=final_text))

    async def _generate(**_kwargs):
        outcome = responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    client = MagicMock()
    client.aio.models.generate_content = _generate
    return client


@pytest.mark.asyncio
async def test_transient_error_is_retried_then_succeeds(service, monkeypatch):
    client = _client_raising(Exception("429 RESOURCE_EXHAUSTED"), final_text="recovered answer")
    monkeypatch.setattr(LLMService, "client", property(lambda _self: client))

    assert await service.generate("prompt") == "recovered answer"


@pytest.mark.asyncio
async def test_permanent_error_is_not_retried(service, monkeypatch):
    attempts = {"count": 0}

    async def _generate(**_kwargs):
        attempts["count"] += 1
        raise Exception("400 INVALID_ARGUMENT: bad request")

    client = MagicMock()
    client.aio.models.generate_content = _generate
    monkeypatch.setattr(LLMService, "client", property(lambda _self: client))

    with pytest.raises(LLMServiceError):
        await service.generate("prompt")

    assert attempts["count"] == 1, "a non-retryable error must not be retried"


@pytest.mark.asyncio
async def test_retries_are_bounded(service, monkeypatch):
    attempts = {"count": 0}

    async def _generate(**_kwargs):
        attempts["count"] += 1
        raise Exception("503 UNAVAILABLE")

    client = MagicMock()
    client.aio.models.generate_content = _generate
    monkeypatch.setattr(LLMService, "client", property(lambda _self: client))

    with pytest.raises(LLMServiceError):
        await service.generate("prompt")

    assert attempts["count"] == 4, "retries must stop at MAX_ATTEMPTS"


def test_prompt_numbers_sources_and_bounds_history():
    service = LLMService()
    history = [{"role": "user", "content": f"turn {i}"} for i in range(20)]

    prompt = service.build_prompt(
        "What is the SLA?",
        [
            {"content": "SLA is 99.95%", "document_name": "strategy.pdf"},
            {"content": "TTFT is 250ms", "document_name": "notes.md"},
        ],
        chat_history=history,
    )

    assert "[Source 1: strategy.pdf]" in prompt
    assert "[Source 2: notes.md]" in prompt
    assert "What is the SLA?" in prompt
    assert "turn 19" in prompt
    assert "turn 0" not in prompt


@pytest.mark.parametrize(
    ("upstream", "expected_fragment"),
    [
        ("429 RESOURCE_EXHAUSTED quotaId: GenerateRequestsPerDay...", "daily quota"),
        ("429 RESOURCE_EXHAUSTED PerMinutePerProject", "rate-limited"),
        ("503 UNAVAILABLE", "temporarily unavailable"),
        ("400 INVALID_ARGUMENT", "could not complete"),
    ],
)
def test_upstream_errors_become_safe_user_messages(upstream, expected_fragment):
    message = LLMService._user_message(Exception(upstream))

    assert expected_fragment in message.lower()
    assert "quotaId" not in message
    assert "http" not in message
    assert "RESOURCE_EXHAUSTED" not in message


@pytest.mark.asyncio
async def test_generation_failure_does_not_leak_provider_payload(service, monkeypatch):
    leaky = (
        "429 RESOURCE_EXHAUSTED. {'error': {'message': 'quota exceeded for "
        "project 12345, see https://ai.google.dev/gemini-api/docs/rate-limits'}}"
    )

    async def _generate(**_kwargs):
        raise Exception(leaky)

    client = MagicMock()
    client.aio.models.generate_content = _generate
    monkeypatch.setattr(LLMService, "client", property(lambda _self: client))

    with pytest.raises(LLMServiceError) as excinfo:
        await service.generate("prompt")

    rendered = str(excinfo.value)
    assert "12345" not in rendered
    assert "ai.google.dev" not in rendered
    assert "rate-limited" in rendered.lower()
