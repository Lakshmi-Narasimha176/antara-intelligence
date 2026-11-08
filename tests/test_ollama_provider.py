import pytest
from unittest import mock
from engine.ollama_provider import OllamaProvider, OllamaProviderError, OllamaModelNotFoundError, LLMTimeoutError

# Helper to build a mock response object
class MockResponse:
    def __init__(self, json_data=None, status_code=200, raise_for_status=None, text=""):
        self._json = json_data or {}
        self.status_code = status_code
        self.ok = (200 <= status_code < 300)
        self.text = text
        self.raise_for_status = mock.Mock()
        if raise_for_status:
            self.raise_for_status.side_effect = raise_for_status
    def json(self):
        return self._json

def test_verify_service_success(monkeypatch):
    mock_resp = MockResponse(json_data={"models": [{"name": "qwen2.5:1.5b"}]})
    monkeypatch.setattr('engine.ollama_provider.requests.get', lambda *args, **kwargs: mock_resp)
    provider = OllamaProvider()
    assert provider.base_url

def test_verify_model_found(monkeypatch):
    model_name = "test-model"
    tags = {"models": [{"name": model_name}]}
    mock_get = mock.Mock(return_value=MockResponse(json_data=tags))
    monkeypatch.setattr('engine.ollama_provider.requests.get', mock_get)
    provider = OllamaProvider(model=model_name)
    # No exception means model found
    assert provider.model == model_name

def test_verify_model_not_found(monkeypatch):
    mock_get = mock.Mock(return_value=MockResponse(json_data={"models": []}))
    monkeypatch.setattr('engine.ollama_provider.requests.get', mock_get)
    with pytest.raises(OllamaModelNotFoundError):
        OllamaProvider(model="missing-model")

def test_generate_success(monkeypatch):
    # Mock tags endpoint
    tags = {"models": [{"name": "test-model"}]}
    mock_get = mock.Mock(return_value=MockResponse(json_data=tags))
    # Mock generate endpoint
    gen_resp = MockResponse(json_data={"response": "Hello", "model": "test-model", "prompt_eval_count": 5, "eval_count": 10})
    mock_post = mock.Mock(return_value=gen_resp)
    monkeypatch.setattr('engine.ollama_provider.requests.get', mock_get)
    monkeypatch.setattr('engine.ollama_provider.requests.post', mock_post)
    provider = OllamaProvider(model="test-model")
    llm_resp = provider.generate(prompt="Hi")
    assert llm_resp.content == "Hello"
    assert llm_resp.provider_name == "ollama"
    assert llm_resp.usage.get("prompt_tokens") == 5
    assert llm_resp.usage.get("completion_tokens") == 10

def test_generate_timeout(monkeypatch):
    tags = {"models": [{"name": "test-model"}]}
    mock_get = mock.Mock(return_value=MockResponse(json_data=tags))
    def raise_timeout(*args, **kwargs):
        raise TimeoutError("timed out")
    mock_post = mock.Mock(side_effect=raise_timeout)
    monkeypatch.setattr('engine.ollama_provider.requests.get', mock_get)
    monkeypatch.setattr('engine.ollama_provider.requests.post', mock_post)
    provider = OllamaProvider(model="test-model")
    with pytest.raises(LLMTimeoutError):
        provider.generate(prompt="test")

def test_generate_network_error(monkeypatch):
    tags = {"models": [{"name": "test-model"}]}
    mock_get = mock.Mock(return_value=MockResponse(json_data=tags))
    def raise_conn_err(*args, **kwargs):
        raise ConnectionError("connection refused")
    mock_post = mock.Mock(side_effect=raise_conn_err)
    monkeypatch.setattr('engine.ollama_provider.requests.get', mock_get)
    monkeypatch.setattr('engine.ollama_provider.requests.post', mock_post)
    provider = OllamaProvider(model="test-model")
    with pytest.raises(OllamaProviderError):
        provider.generate(prompt="test")
