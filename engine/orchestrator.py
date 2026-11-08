"""ANTARĀ Intelligence Engine - Orchestration & Validation Module.

This module provides question validation, initial topic classification, and
structured brief generation for the human-supervised intelligence workflow.
"""

from dataclasses import asdict, dataclass, field
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
        knowledge_context: Verified primary source knowledge attached via retrieval bridge.
        research_context: Modern scientific & empirical research evidence attached via Module 3.
    """

    question: str
    topic: str
    objectives: list[str]
    research_status: str
    status: str
    human_review_required: bool
    created_at_utc: str
    knowledge_context: dict[str, Any] = field(default_factory=dict)
    research_context: dict[str, Any] = field(default_factory=dict)

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


def create_brief(
    question: str,
    kb: Any = None,
    attach_knowledge: bool = True,
    research_mgr: Any = None,
    attach_research: bool = True,
) -> IntelligenceBrief:
    """Create a structured, human-supervised intelligence brief from a question.

    Integrates with Module 2 Knowledge Retrieval Bridge and Module 3 Research
    Intelligence to attach verified primary source knowledge and modern empirical evidence.

    Args:
        question: Raw question submitted by user or client.
        kb: Optional KnowledgeBase instance to use for retrieval.
        attach_knowledge: Whether to query KnowledgeBase for verified knowledge.
        research_mgr: Optional ResearchManager instance for empirical research.
        attach_research: Whether to query ResearchManager for empirical evidence.

    Returns:
        Populated IntelligenceBrief instance with human_review_required=True.
    """
    normalized = validate_question(question)
    topic = classify_topic(normalized)

    knowledge_context: dict[str, Any] = {}
    if attach_knowledge:
        try:
            from engine.retrieval import retrieve_knowledge
            retrieval_result = retrieve_knowledge(normalized, topic=topic, kb=kb)
            knowledge_context = retrieval_result.to_dict()
        except Exception as exc:
            logger.warning("Knowledge retrieval failed during brief creation: %s", exc)
            knowledge_context = {
                "query": normalized,
                "retrieval_indicated": False,
                "status": "error",
                "reason": f"Retrieval bridge error: {exc}",
                "total_found": 0,
                "records": [],
            }

    research_context: dict[str, Any] = {}
    if attach_research:
        try:
            from engine.research import ResearchManager
            mgr = research_mgr if research_mgr is not None else ResearchManager()
            r_ctx = mgr.collect_research_for_question(normalized, topic=topic)
            research_context = r_ctx.to_dict()
        except Exception as exc:
            logger.debug("Research collection skipped or unavailable: %s", exc)
            research_context = {
                "query": normalized,
                "status": "unavailable",
                "reason": f"Research intelligence unavailable: {exc}",
                "total_sources": 0,
                "total_evidence": 0,
                "sources": [],
                "evidence_by_classification": {
                    "supporting": [],
                    "contradicting": [],
                    "contextual": [],
                    "inconclusive": [],
                },
                "evidence_gaps": [],
            }

    brief = IntelligenceBrief(
        question=normalized,
        topic=topic,
        objectives=list(OBJECTIVES),
        research_status="not_started",
        status="brief_created",
        human_review_required=True,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        knowledge_context=knowledge_context,
        research_context=research_context,
    )
    logger.info(
        "Created intelligence brief [topic=%s, human_review_required=%s, knowledge_records=%d, research_evidence=%d]",
        brief.topic,
        brief.human_review_required,
        len(knowledge_context.get("records", [])),
        research_context.get("total_evidence", 0),
    )
    return brief

