"""ANTARĀ Intelligence Engine - LLM Provider Interface.

Defines the provider-independent abstraction layer for AI reasoning models,
normalized message schemas, structured output contracts, error hierarchies,
and deterministic mock providers for offline testing.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
import json
import logging
from typing import Any

from engine.orchestrator import AntaraError

logger = logging.getLogger("antara.llm_provider")


class LLMError(AntaraError):
    """Base exception for all LLM provider errors."""


class LLMConfigError(LLMError):
    """Raised when provider configuration is invalid or missing credentials."""


class LLMTimeoutError(LLMError):
    """Raised when an LLM provider request exceeds its allotted timeout."""


class LLMRefusalError(LLMError):
    """Raised when an LLM explicitly refuses to generate a response."""


class LLMIncompleteResponseError(LLMError):
    """Raised when an LLM response is truncated (e.g., finish_reason == 'length')."""


class LLMRateLimitError(LLMError):
    """Raised when provider rate limits are exceeded."""


class LLMAuthenticationError(LLMError):
    """Raised when provider credentials are rejected."""


@dataclass(frozen=True)
class LLMMessage:
    """A single chat message in a provider-independent conversation."""

    role: str  # "system", "user", "assistant"
    content: str

    def to_dict(self) -> dict[str, str]:
        """Convert message to dictionary."""
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class LLMResponse:
    """Normalized response returned by any LLM provider."""

    content: str
    model: str
    finish_reason: str
    refusal: str | None = None
    raw_json: dict[str, Any] | None = None
    usage: dict[str, int] = field(default_factory=dict)
    provider_name: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        """Convert response to dictionary."""
        return asdict(self)


class LLMProvider(ABC):
    """Abstract base class for all ANTARĀ LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier for this provider implementation."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Current model identifier in use."""
        pass

    @abstractmethod
    def generate(
        self,
        messages: list[LLMMessage | dict[str, str]],
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Generate a response from the provider given input messages.

        Args:
            messages: List of chat messages (LLMMessage or dicts).
            json_mode: Whether to enforce valid JSON structured output.
            temperature: Sampling temperature (default 0.2 for analytical rigor).

        Returns:
            Normalized LLMResponse instance.

        Raises:
            LLMTimeoutError: If the request times out.
            LLMRefusalError: If the model refuses to respond.
            LLMIncompleteResponseError: If the response is truncated.
            LLMAuthenticationError: If API credentials fail.
            LLMError: For other unrecoverable errors.
        """
        pass

    def generate_prompt(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Convenience method to generate from a simple user/system prompt pair."""
        messages: list[LLMMessage] = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=user_prompt))
        return self.generate(messages, json_mode=json_mode, temperature=temperature)


class MockLLMProvider(LLMProvider):
    """Deterministic mock provider for offline testing and development without API keys."""

    def __init__(
        self,
        model: str = "mock-reasoner-v1",
        mock_response: str | dict[str, Any] | None = None,
        should_fail: Exception | None = None,
        should_refuse: bool = False,
        incomplete: bool = False,
        recorded_messages: list[list[dict[str, str]]] | None = None,
    ) -> None:
        """Initialize mock provider with controllable behavioral fixtures."""
        self._model = model
        self.mock_response = mock_response
        self.should_fail = should_fail
        self.should_refuse = should_refuse
        self.incomplete = incomplete
        self.recorded_messages: list[list[dict[str, str]]] = recorded_messages if recorded_messages is not None else []

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model

    def generate(
        self,
        messages: list[LLMMessage | dict[str, str]],
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Generate mock response or raise configured failure."""
        # Record invocation for test assertions
        norm_msgs = [m.to_dict() if isinstance(m, LLMMessage) else m for m in messages]
        self.recorded_messages.append(norm_msgs)

        if self.should_fail:
            raise self.should_fail

        if self.should_refuse:
            raise LLMRefusalError("Mock LLM refused to generate a response.")

        if self.incomplete:
            raise LLMIncompleteResponseError("Mock LLM response truncated (finish_reason: length).")

        raw_json: dict[str, Any] | None = None
        if self.mock_response is not None:
            if isinstance(self.mock_response, dict):
                raw_json = self.mock_response
                content = json.dumps(self.mock_response, ensure_ascii=False)
            else:
                content = str(self.mock_response)
                if json_mode:
                    try:
                        raw_json = json.loads(content)
                    except Exception:
                        pass
        else:
            # Default authentic mock synthesis response
            default_payload: dict[str, Any] = {
                "executive_summary": "Analysis indicates a synthesis between action without attachment and temporal motivation theory.",
                "philosophical_perspective": "The Bhagavad Gita presents Niṣkāma Karma as duty without anxiety for fruit.",
                "relevant_gita_teachings": [
                    {
                        "verse_id": 1,
                        "chapter": 2,
                        "verse": 47,
                        "teaching": "Stewardship over effort, no entitlement to fruit.",
                        "sanskrit_quote": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
                        "translation_quote": "To action alone hast thou a right and never at all to its fruits",
                    }
                ],
                "modern_scientific_perspectives": "Modern psychology explains procrastination as self-regulatory failure.",
                "supporting_research_evidence": [
                    {
                        "evidence_id": 1,
                        "source_id": 1,
                        "finding": "Procrastination correlates strongly with impulsiveness and delay discounting (r = 0.41).",
                    }
                ],
                "contradicting_research_evidence": [],
                "philosophical_and_scientific_similarities": [
                    "Both frameworks identify cognitive focus on distal reward as a key failure mode."
                ],
                "important_differences": [
                    "Bhagavad Gita frames detachment within metaphysical ontology; modern psychology focuses on cognitive regulation."
                ],
                "critical_analysis": "While complementary, modern science examines behavioral mechanisms whereas the Gita addresses existential purpose.",
                "original_synthesized_insight": "Detachment from fruits reduces cognitive discounting of immediate effort, stabilizing agency.",
                "practical_implications": [
                    "Focus attention strictly on current actionable process rather than hypothetical outcome metrics."
                ],
                "limitations_and_uncertainty": [
                    "Empirical research is predominantly correlational; cross-paradigm comparisons must respect domain boundaries."
                ],
                "research_gaps": [
                    "Interventional trials combining mindfulness detachment with temporal scheduling."
                ],
                "exact_source_citations": [
                    {"type": "gita", "id": 1, "locator": "Chapter 2, Verse 47"},
                    {"type": "research", "id": 1, "doi": "10.1037/0033-2909.133.1.65"},
                ],
                "claims_requiring_human_review": [
                    {
                        "claim_id": "mock_c1",
                        "claim_text": "To action alone hast thou a right and never at all to its fruits",
                        "source_type": "gita",
                        "record_id": 1,
                        "chapter": 2,
                        "verse": 47,
                        "is_direct_quote": True,
                        "quoted_text": "To action alone hast thou a right and never at all to its fruits",
                        "quote_field": "translation",
                    }
                ],
            }
            raw_json = default_payload
            content = json.dumps(default_payload, ensure_ascii=False)

        return LLMResponse(
            content=content,
            model=self._model,
            finish_reason="stop",
            refusal=None,
            raw_json=raw_json,
            usage={"prompt_tokens": 120, "completion_tokens": 280, "total_tokens": 400},
            provider_name=self.provider_name,
        )
