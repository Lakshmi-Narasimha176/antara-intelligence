"""ANTARĀ Intelligence Engine - OpenAI Provider Implementation.

Integrates with the official OpenAI Python SDK to deliver structured,
deterministic reasoning while strictly adhering to security, timeout,
retry, and error-handling requirements.
"""

import json
import logging
import os
from typing import Any

import openai

from engine.llm_provider import (
    LLMAuthenticationError,
    LLMConfigError,
    LLMError,
    LLMIncompleteResponseError,
    LLMMessage,
    LLMProvider,
    LLMRateLimitError,
    LLMRefusalError,
    LLMResponse,
    LLMTimeoutError,
)

logger = logging.getLogger("antara.openai_provider")

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 2


class OpenAIProvider(LLMProvider):
    """OpenAI reasoning provider powered by the official SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        client: Any = None,
    ) -> None:
        """Initialize the OpenAI provider using environment variables or explicit parameters.

        Args:
            api_key: Optional API key. Defaults to OPENAI_API_KEY environment variable.
            model: Optional model identifier. Defaults to OPENAI_MODEL or 'gpt-4o-mini'.
            timeout: Optional request timeout in seconds. Defaults to OPENAI_TIMEOUT or 30.0.
            max_retries: Optional maximum retry attempts. Defaults to OPENAI_MAX_RETRIES or 2.
            client: Optional injected OpenAI client (useful for unit testing without live network).

        Raises:
            LLMConfigError: If API key is missing or invalid.
        """
        raw_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self._api_key = raw_key.strip() if isinstance(raw_key, str) else ""

        raw_model = model if model is not None else os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        self._model = raw_model.strip() if isinstance(raw_model, str) and raw_model.strip() else DEFAULT_MODEL

        # Timeout validation
        if timeout is not None:
            self._timeout = float(timeout)
        else:
            try:
                self._timeout = float(os.environ.get("OPENAI_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS)))
            except (ValueError, TypeError):
                self._timeout = DEFAULT_TIMEOUT_SECONDS

        if self._timeout <= 0:
            raise LLMConfigError(f"OPENAI_TIMEOUT must be a positive float, got {self._timeout}")

        # Retries validation
        if max_retries is not None:
            self._max_retries = int(max_retries)
        else:
            try:
                self._max_retries = int(os.environ.get("OPENAI_MAX_RETRIES", str(DEFAULT_MAX_RETRIES)))
            except (ValueError, TypeError):
                self._max_retries = DEFAULT_MAX_RETRIES

        if self._max_retries < 0:
            raise LLMConfigError(f"OPENAI_MAX_RETRIES must be non-negative, got {self._max_retries}")

        # Allow injected client for testing; otherwise construct OpenAI client if key is present
        if client is not None:
            self._client = client
        elif self._api_key:
            self._client = openai.OpenAI(
                api_key=self._api_key,
                timeout=self._timeout,
                max_retries=self._max_retries,
            )
        else:
            self._client = None

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    def _ensure_client(self) -> Any:
        """Verify client availability before executing a request."""
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise LLMConfigError(
                "OPENAI_API_KEY environment variable is not configured. "
                "Set OPENAI_API_KEY in your local environment or use MockLLMProvider for offline execution."
            )
        self._client = openai.OpenAI(
            api_key=self._api_key,
            timeout=self._timeout,
            max_retries=self._max_retries,
        )
        return self._client

    def generate(
        self,
        messages: list[LLMMessage | dict[str, str]],
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Execute a chat completion request via OpenAI SDK."""
        client = self._ensure_client()

        # Format input messages
        formatted_messages: list[dict[str, str]] = []
        for msg in messages:
            if isinstance(msg, LLMMessage):
                formatted_messages.append(msg.to_dict())
            elif isinstance(msg, dict) and "role" in msg and "content" in msg:
                formatted_messages.append({"role": msg["role"], "content": msg["content"]})
            else:
                raise LLMConfigError(f"Invalid message format: {msg}")

        params: dict[str, Any] = {
            "model": self._model,
            "messages": formatted_messages,
            "temperature": temperature,
        }
        if json_mode:
            params["response_format"] = {"type": "json_object"}

        try:
            completion = client.chat.completions.create(**params)
        except openai.AuthenticationError as exc:
            logger.error("OpenAI authentication error: %s", exc)
            raise LLMAuthenticationError(f"OpenAI authentication failed: {exc}") from exc
        except openai.RateLimitError as exc:
            logger.warning("OpenAI rate limit reached: %s", exc)
            raise LLMRateLimitError(f"OpenAI rate limit exceeded: {exc}") from exc
        except openai.APITimeoutError as exc:
            logger.warning("OpenAI request timed out after %s seconds: %s", self._timeout, exc)
            raise LLMTimeoutError(f"OpenAI request timed out after {self._timeout}s: {exc}") from exc
        except openai.APIConnectionError as exc:
            logger.error("OpenAI connection error: %s", exc)
            raise LLMError(f"OpenAI connection failure: {exc}") from exc
        except openai.APIStatusError as exc:
            logger.error("OpenAI HTTP status error %s: %s", exc.status_code, exc)
            raise LLMError(f"OpenAI API status error {exc.status_code}: {exc}") from exc
        except openai.OpenAIError as exc:
            logger.error("OpenAI SDK general error: %s", exc)
            raise LLMError(f"OpenAI request failed: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error during OpenAI request: %s", exc)
            raise LLMError(f"Unexpected provider error: {exc}") from exc

        if not completion.choices:
            raise LLMError("OpenAI returned an empty choices list.")

        choice = completion.choices[0]

        # Check refusal
        refusal = getattr(choice.message, "refusal", None)
        if refusal:
            logger.warning("OpenAI model refusal: %s", refusal)
            raise LLMRefusalError(f"OpenAI model refused request: {refusal}")

        # Check finish_reason
        finish_reason = choice.finish_reason or "unknown"
        if finish_reason == "length":
            logger.error("OpenAI completion truncated due to token length limit.")
            raise LLMIncompleteResponseError("OpenAI response truncated by token limit (finish_reason: length).")

        content = choice.message.content or ""

        # Parse JSON if requested
        raw_json: dict[str, Any] | None = None
        if json_mode:
            try:
                raw_json = json.loads(content)
            except Exception as exc:
                logger.warning("Failed to parse JSON response from model '%s': %s", self._model, exc)

        usage_dict: dict[str, int] = {}
        if completion.usage:
            usage_dict = {
                "prompt_tokens": completion.usage.prompt_tokens,
                "completion_tokens": completion.usage.completion_tokens,
                "total_tokens": completion.usage.total_tokens,
            }

        return LLMResponse(
            content=content,
            model=completion.model,
            finish_reason=finish_reason,
            refusal=refusal,
            raw_json=raw_json,
            usage=usage_dict,
            provider_name=self.provider_name,
        )
