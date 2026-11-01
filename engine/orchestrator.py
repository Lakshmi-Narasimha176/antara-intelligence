"""ANTARĀ Intelligence Engine - Orchestration & Validation Module.

This module provides question validation, initial topic classification, and
structured brief generation for the human-supervised intelligence workflow.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import logging
from typing import Any

# Structured logger for orchestration events
logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH: int = 500
OBJECTIVES: tuple[str, ...] = (
    "Clarify the question and identify assumptions.",
    "Separate facts, interpretations, and hypotheses.",
    "Identify credible sources before making factual claims.",
    "Propose a practical experiment only when supported by evidence.",
)


class AntaraError(Exception):
    """Base exception for all ANTARĀ Intelligence Engine domain errors."""


class ValidationError(AntaraError, ValueError):
    """Raised when question content violates validation constraints."""


class QuestionTypeError(AntaraError, TypeError):
    """Raised when question input is not of expected string type."""


@dataclass(frozen=True)
class IntelligenceBrief:
    """Structured research brief requiring human review.

    Attributes:
        question: Normalized user question.
        topic: Classified subject category.
        objectives: Foundational research objectives to guide investigation.
        research_status: Progress state of automated research (e.g., 'not_started').
        status: Overall status of the intelligence brief.
        human_review_required: Flag enforcing mandatory human supervision.
        created_at_utc: ISO 8601 UTC timestamp of brief creation.
    """

    question: str
    topic: str
    objectives: list[str]
    research_status: str
    status: str
    human_review_required: bool
    created_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        """Convert intelligence brief to a JSON-serializable dictionary."""
        return asdict(self)


def validate_question(question: str) -> str:
    """Validate and normalize an incoming user research question.

    Args:
        question: Raw user question string.

    Returns:
        Whitespace-normalized question string.

    Raises:
        QuestionTypeError: If question is not a string (subclass of TypeError).
        ValidationError: If question is empty or exceeds character limits (subclass of ValueError).
    """
    if not isinstance(question, str):
        logger.error("Question validation failed: input type %s is not str", type(question).__name__)
        raise QuestionTypeError("Question must be a string.")
    normalized = " ".join(question.split())
    if not normalized:
        logger.error("Question validation failed: empty string after normalization.")
        raise ValidationError("Question cannot be empty.")
    if len(normalized) > MAX_QUESTION_LENGTH:
        logger.error(
            "Question validation failed: length %d exceeds limit of %d.",
            len(normalized),
            MAX_QUESTION_LENGTH,
        )
        raise ValidationError(f"Question must be {MAX_QUESTION_LENGTH} characters or fewer.")
    return normalized


def classify_topic(question: str) -> str:
    """Classify the research question into an initial domain topic.

    Keyword heuristics are applied case-insensitively.

    Args:
        question: Input question text.

    Returns:
        Identified topic slug string ('human_behavior', 'philosophy',
        'technology', 'productivity', or fallback 'general').
    """
    text = question.casefold()
    categories: dict[str, tuple[str, ...]] = {
        "human_behavior": ("procrastination", "procrastinate", "habit", "emotion", "fear", "motivation"),
        "philosophy": ("meaning", "purpose", "dharma", "ethics", "wisdom", "bhagavad", "gita"),
        "technology": ("ai", "software", "computer", "algorithm", "technology", "python"),
        "productivity": ("focus", "time management", "goal", "work", "productivity"),
    }
    for topic, keywords in categories.items():
        if any(keyword in text for keyword in keywords):
            logger.debug("Classified question under topic '%s'", topic)
            return topic
    logger.debug("No keyword match found; defaulting to topic 'general'")
    return "general"


def create_brief(question: str) -> IntelligenceBrief:
    """Create a structured, human-supervised intelligence brief from a question.

    Args:
        question: Raw question submitted by user or client.

    Returns:
        Populated IntelligenceBrief instance with human_review_required=True.
    """
    normalized = validate_question(question)
    topic = classify_topic(normalized)
    brief = IntelligenceBrief(
        question=normalized,
        topic=topic,
        objectives=list(OBJECTIVES),
        research_status="not_started",
        status="brief_created",
        human_review_required=True,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    logger.info(
        "Created intelligence brief [topic=%s, human_review_required=%s]",
        brief.topic,
        brief.human_review_required,
    )
    return brief

