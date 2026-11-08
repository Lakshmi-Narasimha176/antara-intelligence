'''engine.ollama_provider

Implementation of the LLMProvider abstraction for a local Ollama server.
Supports text generation and optional JSON mode.  The provider is deliberately
lightweight and uses the HTTP API exposed by Ollama (v0.40+).
This provider enables ANTARĀ to run locally without external API keys.
'''

import os
import json
import logging
from typing import Any, List

import requests

from engine.llm_provider import (
    LLMProvider,
    LLMMessage,
    LLMResponse,
    LLMError,
    LLMTimeoutError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMIncompleteResponseError,
)

logger = logging.getLogger("antara.ollama_provider")

class OllamaProviderError(LLMError):
    """Base exception for Ollama‑specific errors."""

class OllamaModelNotFoundError(OllamaProviderError):
    """Raised when the configured model is not installed on the Ollama server."""

class OllamaProvider(LLMProvider):
    """Concrete LLMProvider that talks to a local Ollama instance.

    Configuration is read from environment variables:
        - ``ANTARA_OLLAMA_BASE_URL`` – base URL of the Ollama HTTP server
          (default ``http://localhost:11434``).
        - ``ANTARA_OLLAMA_MODEL`` – model name to use (e.g. ``qwen2.5:1.5b``).
        - ``ANTARA_OLLAMA_TIMEOUT`` – request timeout in seconds (default 120).
    """

    def __init__(self, model: str | None = None) -> None:
        # Base URL configuration
        self.base_url = os.getenv("ANTARA_OLLAMA_BASE_URL", "http://localhost:11434").rstrip('/')
        # Resolve model: explicit argument overrides environment variable
        self.model = model if model is not None else os.getenv("ANTARA_OLLAMA_MODEL", "qwen2.5:1.5b")
        self.timeout = int(os.getenv("ANTARA_OLLAMA_TIMEOUT", "120"))
        # Cache for tags to avoid duplicate network calls
        self._tags_cache: dict[str, Any] | None = None
        self._verify_service()
        self._verify_model()

    # ---------------------------------------------------------------------
    # Provider metadata
    # ---------------------------------------------------------------------
    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self.model

    # ---------------------------------------------------------------------
    # Internal helpers – GET and POST handling
    # ---------------------------------------------------------------------
    def _get(self, endpoint: str) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, timeout=self.timeout)
        except requests.Timeout as exc:
            raise LLMTimeoutError(f"Ollama GET request timed out after {self.timeout}s") from exc
        except Exception as exc:
            # Catch generic timeouts (e.g., built‑in TimeoutError) and other request failures
            if isinstance(exc, TimeoutError):
                raise LLMTimeoutError(f"Ollama GET request timed out after {self.timeout}s") from exc
            raise OllamaProviderError(f"Network error during Ollama GET: {exc}") from exc

        if response.status_code == 401:
            raise LLMAuthenticationError("Ollama authentication failed (unexpected).")
        if response.status_code == 429:
            raise LLMRateLimitError("Ollama rate limit exceeded.")
        ok = getattr(response, "ok", response.status_code == 200)
        if not ok:
            raise OllamaProviderError(f"Ollama GET returned HTTP {response.status_code}: {response.text}")

        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise OllamaProviderError("Failed to parse Ollama GET JSON response.") from exc

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
        except requests.Timeout as exc:
            raise LLMTimeoutError(f"Ollama POST request timed out after {self.timeout}s") from exc
        except Exception as exc:
            if isinstance(exc, TimeoutError):
                raise LLMTimeoutError(f"Ollama POST request timed out after {self.timeout}s") from exc
            raise OllamaProviderError(f"Network error during Ollama POST: {exc}") from exc

        if response.status_code == 401:
            raise LLMAuthenticationError("Ollama authentication failed (unexpected).")
        if response.status_code == 429:
            raise LLMRateLimitError("Ollama rate limit exceeded.")
        ok = getattr(response, "ok", 200 <= getattr(response, "status_code", 200) < 300)
        if not ok:
            raise OllamaProviderError(f"Ollama POST returned HTTP {response.status_code}: {response.text}")

        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise OllamaProviderError("Failed to parse Ollama POST JSON response.") from exc

    # ---------------------------------------------------------------------
    # Service / model verification
    # ---------------------------------------------------------------------
    def _verify_service(self) -> None:
        """Ensure the Ollama HTTP endpoint is reachable.

        A simple GET on ``/api/tags`` returns a list of installed models.
        """
        self._tags_cache = self._get("/api/tags")

    def _verify_model(self) -> None:
        """Check that ``self.model`` exists among the installed tags.

        Uses the cached result from ``_verify_service`` to avoid a second request.
        """
        if self._tags_cache is None:
            self._tags_cache = self._get("/api/tags")
        installed = {m.get("name") for m in self._tags_cache.get("models", [])}
        if self.model not in installed:
            raise OllamaModelNotFoundError(
                f"Model '{self.model}' not found in Ollama. Install it with: ollama pull {self.model}"
            )


    # ---------------------------------------------------------------------
    # Public API – generate
    # ---------------------------------------------------------------------
    def generate(
        self,
        messages: List[LLMMessage | dict[str, str]] | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
        *,
        prompt: str | None = None,
    ) -> LLMResponse:
        """Generate a response using the Ollama ``/api/generate`` endpoint.

        Supports the historic ``prompt=`` keyword for backward compatibility used in tests.
        If ``prompt`` is provided, it is wrapped into a single user message.
        """
        if prompt is not None:
            messages = [LLMMessage(role="user", content=prompt)]
        if messages is None:
            raise ValueError("Either messages list or prompt must be provided")
        """Generate a response using the Ollama ``/api/generate`` endpoint.

        Args:
            messages: List of chat messages. Only the ``content`` field is required;
                the ``role`` is passed verbatim to Ollama (``system`` or ``user``).
                Ollama does not differentiate ``assistant`` role but we preserve it
                for API compatibility.
            json_mode: When ``True`` the model is instructed to emit valid JSON.
                We attempt to parse the ``response`` field as JSON; if parsing fails
                the raw string is returned and ``raw_json`` remains ``None``.
            temperature: Sampling temperature – forwarded to Ollama.
        """
        prompt_parts: List[str] = []
        for msg in messages:
            if isinstance(msg, LLMMessage):
                role, content = msg.role, msg.content
            else:
                role, content = msg.get("role"), msg.get("content")
            if role == "system":
                prompt_parts.append(f"[SYSTEM] {content}")
            else:
                prompt_parts.append(content)
        prompt = "\n".join(prompt_parts)

        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": temperature,
        }
        if json_mode:
            payload["system"] = "Respond with valid JSON."

        response_json = self._post("/api/generate", payload)
        raw_text: str = response_json.get("response", "").strip()
        if not raw_text:
            raise LLMIncompleteResponseError("Ollama returned an empty response.")

        refusal_phrases = ["I cannot answer", "I am not able to", "I do not have information"]
        if any(p.lower() in raw_text.lower() for p in refusal_phrases):
            raise LLMRefusalError("Ollama refused to generate a response.")

        raw_json: dict[str, Any] | None = None
        if json_mode:
            try:
                raw_json = json.loads(raw_text)
            except Exception:
                logger.debug("Ollama JSON mode parsing failed; returning raw text.")

        usage: dict[str, int] = {}
        if "prompt_eval_count" in response_json:
            usage["prompt_tokens"] = response_json["prompt_eval_count"]
        if "eval_count" in response_json:
            usage["completion_tokens"] = response_json["eval_count"]

        return LLMResponse(
            content=raw_text,
            model=self.model,
            finish_reason="stop" if response_json.get("done", True) else "length",
            refusal=None,
            raw_json=raw_json,
            usage=usage,
            provider_name=self.provider_name,
        )
