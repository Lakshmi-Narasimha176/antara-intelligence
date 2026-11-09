"""Acceptance checks for explicit, deterministic local-first offline operation."""

import socket
from typing import Any, NoReturn
from unittest.mock import Mock

import httpx2 as httpx
import pytest
import requests

from engine.llm_provider import LLMMessage, MockLLMProvider
from engine.ollama_provider import OllamaModelNotFoundError, OllamaProvider, OllamaProviderError
from engine.search import MockSearchProvider, OpenAIWebSearchProvider
from engine.unified_engine import UnifiedEngine


def _deny_network(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError(
        f"Offline execution attempted network access: args={_args!r}, kwargs={_kwargs!r}"
    )


def test_mock_providers_and_unified_pipeline_run_without_network(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTARA_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(socket.socket, "connect", _deny_network)
    monkeypatch.setattr(socket, "create_connection", _deny_network)
    monkeypatch.setattr(httpx.Client, "send", _deny_network)
    monkeypatch.setattr(requests.sessions.Session, "request", _deny_network)

    engine = UnifiedEngine(db_path=tmp_path / "offline.db")
    assert isinstance(engine.llm_provider, MockLLMProvider)

    search_response = MockSearchProvider().search("offline evidence")
    assert search_response.status == "completed"
    assert search_response.total_results > 0

    class LocalResponse:
        status_code = 200
        ok = True
        text = ""

        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data

    monkeypatch.setenv("ANTARA_OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setattr(
        "engine.ollama_provider.requests.get",
        Mock(return_value=LocalResponse({"models": [{"name": "local-test-model"}]})),
    )
    local_generate = Mock(return_value=LocalResponse({
        "response": "Local inference succeeded.",
        "model": "local-test-model",
    }))
    monkeypatch.setattr("engine.ollama_provider.requests.post", local_generate)
    local_response = OllamaProvider(model="local-test-model").generate(
        [LLMMessage(role="user", content="offline local inference")]
    )
    assert local_response.provider_name == "ollama"
    assert local_response.content == "Local inference succeeded."
    assert local_generate.call_args.args[0].startswith("http://localhost:11434/")

    _, analysis, _ = engine.process(
        "Why does focused effort matter?",
        force_knowledge=False,
        force_research=False,
        force_web=False,
    )
    assert analysis.report_id
    assert analysis.human_review_required is True


def test_ollama_failure_never_falls_back_to_cloud(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTARA_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "engine.ollama_provider.requests.get",
        Mock(side_effect=requests.ConnectionError("local Ollama unavailable")),
    )

    def reject_cloud_fallback(*_args: object, **_kwargs: object) -> NoReturn:
        pytest.fail(
            "An explicitly selected local provider must not fall back to OpenAI: "
            f"args={_args!r}, kwargs={_kwargs!r}"
        )

    monkeypatch.setattr("engine.unified_engine.OpenAIProvider", reject_cloud_fallback)

    with pytest.raises(OllamaProviderError, match="local Ollama unavailable"):
        UnifiedEngine(db_path=tmp_path / "local-only.db")


def test_missing_local_model_is_not_downloaded_automatically(monkeypatch):
    class TagsResponse:
        status_code = 200
        ok = True
        text = ""

        def __init__(self) -> None:
            self.data: dict[str, list[Any]] = {"models": []}

        def json(self) -> dict[str, list[Any]]:
            return self.data

    mock_get = Mock(return_value=TagsResponse())
    mock_post = Mock()
    monkeypatch.setattr("engine.ollama_provider.requests.get", mock_get)
    monkeypatch.setattr("engine.ollama_provider.requests.post", mock_post)

    with pytest.raises(OllamaModelNotFoundError):
        OllamaProvider(model="not-installed")

    mock_get.assert_called_once()
    mock_post.assert_not_called()


def test_unavailable_network_search_reports_unavailable_without_credentials():
    response = OpenAIWebSearchProvider(api_key="").search("latest research")

    assert response.status == "unavailable"
    assert response.total_results == 0
    assert "not configured" in response.disclosure_note
