"""ANTARĀ Intelligence Engine - Orchestration & Validation Module.

This module provides question validation, initial topic classification, intelligent
subsystem routing, and structured brief generation for the human-supervised intelligence workflow.
"""

from dataclasses import asdict, dataclass, field
from engine.language import detect_language, identify_dialect
from datetime import datetime, timezone
import logging
import re
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

TRADITIONAL_KEYWORDS = frozenset({
    "bhagavad", "gita", "gītā", "dharma", "karma", "krishna", "arjuna",
    "yoga", "vedanta", "upanishad", "sanskrit", "verse", "shloka",
    "chapter", "samkhya", "moksha", "nishkama", "niṣkāma", "atman", "brahman",
})

RESEARCH_KEYWORDS = frozenset({
    "study", "studies", "research", "science", "scientific", "psychology",
    "psychological", "neuroscience", "empirical", "experiment", "cognitive",
    "delay discounting", "procrastination", "dopamine", "prefrontal",
    "behavior", "meta-analysis", "hypothesis", "clinical", "sample size",
})

LIVE_INTERNET_KEYWORDS = frozenset({
    "current", "currently", "latest", "recent", "recently", "today", "now",
    "2024", "2025", "2026", "newest", "trend", "trends", "update", "updates",
    "news", "ongoing", "policy", "breakthrough", "breakthroughs", "market",
    "live", "real-time", "developments",
})


class AntaraError(Exception):
    """Base exception for all ANTARĀ Intelligence Engine domain errors."""


class ValidationError(AntaraError, ValueError):
    """Raised when question content violates validation constraints."""


class QuestionTypeError(AntaraError, TypeError):
    """Raised when question input is not of expected string type."""


@dataclass(frozen=True)
class SubsystemPlan:
    """Intelligent subsystem execution plan determining which engines to invoke.

    Attributes:
        question: Normalized query string.
        needs_traditional_knowledge: Whether Bhagavad Gītā knowledge is indicated.
        needs_scientific_research: Whether empirical scientific research is indicated.
        needs_live_internet: Whether real-time web retrieval is indicated.
        needs_reasoning: Whether AI comparative reasoning synthesis is indicated.
        selection_rationale: Detailed explanation of routing decisions.
    """

    question: str
    needs_traditional_knowledge: bool
    needs_scientific_research: bool
    needs_live_internet: bool
    needs_reasoning: bool
    selection_rationale: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        """Convert plan to dictionary."""
        return asdict(self)


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
        validation_context: Module 4 Anti-Hallucination & Fact-Checking report context.
        web_context: Real-time web intelligence and search context attached via Part A.
        subsystem_plan: Intelligent routing plan recording which subsystems were invoked.
        query_language: Detected language of the input query (telugu, english, mixed, unknown).
        response_language: Preferred language for the final response (defaults to query language if known).
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
    validation_context: dict[str, Any] = field(default_factory=dict)
    web_context: dict[str, Any] = field(default_factory=dict)
    subsystem_plan: dict[str, Any] = field(default_factory=dict)
    query_language: str = "unknown"
    response_language: str = "english"
    dialect: str | None = None
    code_switching: dict[str, Any] | None = None

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
        "technology": ("ai", "software", "computer", "algorithm", "technology", "python", "quantum"),
        "productivity": ("focus", "time management", "goal", "work", "productivity"),
    }
    for topic, keywords in categories.items():
        if any(keyword in text for keyword in keywords):
            logger.debug("Classified question under topic '%s'", topic)
            return topic
    logger.debug("No keyword match found; defaulting to topic 'general'")
    return "general"


def classify_subsystems(question: str) -> SubsystemPlan:
    """Intelligently determine which subsystems should be invoked for a given question.

    Evaluates whether the question requires traditional Gītā knowledge, empirical
    scientific research, real-time web intelligence, and AI reasoning.

    Args:
        question: Normalized user question string.

    Returns:
        SubsystemPlan instance detailing active subsystems and routing rationales.
    """
    text = question.casefold()
    tokens = set(re.findall(r"\b[\w\-]+\b", text))

    # 1. Traditional Knowledge
    has_gita_verse_ref = bool(re.search(r"\b(chapter\s+\d+|\d+\s*[\.:]\s*\d+|bg\s*\d+)\b", text))
    has_traditional_kw = bool(tokens & TRADITIONAL_KEYWORDS) or any(kw in text for kw in ("bhagavad gita", "bhagavad gītā"))
    needs_traditional = has_traditional_kw or has_gita_verse_ref or (classify_topic(question) == "philosophy" and not (tokens & LIVE_INTERNET_KEYWORDS))

    # 2. Scientific Research
    has_research_kw = bool(tokens & RESEARCH_KEYWORDS) or any(kw in text for kw in ("delay discounting", "cognitive science", "mental health"))
    needs_research = has_research_kw or classify_topic(question) in ("human_behavior", "productivity")

    # 3. Live Internet Intelligence
    has_live_kw = bool(tokens & LIVE_INTERNET_KEYWORDS) or any(kw in text for kw in ("real time", "real-time", "as of"))
    needs_live = has_live_kw or (classify_topic(question) == "technology" and not has_traditional_kw)

    # 4. Reasoning
    needs_reasoning = True  # Always available for synthesis when requested

    rationale = {
        "traditional_knowledge": (
            "Indicated by explicit Gītā keywords or philosophical citation references."
            if needs_traditional
            else "Bypassed: Question does not indicate traditional scriptural or Gītā inquiry."
        ),
        "scientific_research": (
            "Indicated by empirical research, psychology, or behavioral keywords."
            if needs_research
            else "Bypassed: Question does not indicate empirical scientific research."
        ),
        "live_internet": (
            "Indicated by temporal keywords ('recent', 'latest', '2026', 'current') or real-time topics."
            if needs_live
            else "Bypassed: Question does not require real-time web retrieval."
        ),
        "reasoning": "Available for structured synthesis and multi-domain comparative analysis.",
    }

    return SubsystemPlan(
        question=question,
        needs_traditional_knowledge=needs_traditional,
        needs_scientific_research=needs_research,
        needs_live_internet=needs_live,
        needs_reasoning=needs_reasoning,
        selection_rationale=rationale,
    )


def create_brief(
    question: str,
    kb: Any = None,
    attach_knowledge: bool = True,
    research_mgr: Any = None,
    attach_research: bool = True,
    claims: list[Any] | None = None,
    fact_checker: Any = None,
    search_mgr: Any = None,
    attach_web: bool = True,
    force_knowledge: bool | None = None,
    force_research: bool | None = None,
    force_web: bool | None = None,
) -> IntelligenceBrief:
    """Create a structured, human-supervised intelligence brief from a question.

    Intelligently integrates with:
    - Traditional Knowledge Retrieval Bridge (Module 2)
    - Modern Scientific Research Intelligence (Module 3)
    - Anti-Hallucination & Fact-Checking Engine (Module 4)
    - Real-Time Live Web Intelligence (Part A)

    Args:
        question: Raw question submitted by user or client.
        kb: Optional KnowledgeBase instance to use for retrieval.
        attach_knowledge: Whether to query KnowledgeBase if indicated.
        research_mgr: Optional ResearchManager instance for empirical research.
        attach_research: Whether to query ResearchManager if indicated.
        claims: Optional list of Claim objects or dicts to fact-check.
        fact_checker: Optional FactChecker instance to use for validation.
        search_mgr: Optional SearchManager instance for live web retrieval.
        attach_web: Whether to query SearchManager if indicated.
        force_knowledge: Explicit override to force or bypass traditional retrieval.
        force_research: Explicit override to force or bypass research retrieval.
        force_web: Explicit override to force or bypass live web retrieval.

    Returns:
        Populated IntelligenceBrief instance with human_review_required=True.
    """
    normalized = validate_question(question)
    topic = classify_topic(normalized)
    plan = classify_subsystems(normalized)

    # Determine subsystem invocations (overrides take precedence if provided)
    run_knowledge = plan.needs_traditional_knowledge if force_knowledge is None else force_knowledge
    run_research = plan.needs_scientific_research if force_research is None else force_research
    run_web = plan.needs_live_internet if force_web is None else force_web

    # 1. Traditional Knowledge Retrieval
    knowledge_context: dict[str, Any] = {}
    if attach_knowledge:
        if run_knowledge:
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
        else:
            knowledge_context = {
                "query": normalized,
                "retrieval_indicated": False,
                "status": "retrieval_not_indicated",
                "reason": plan.selection_rationale["traditional_knowledge"],
                "total_found": 0,
                "records": [],
            }

    # 2. Scientific & Empirical Research Intelligence
    research_context: dict[str, Any] = {}
    if attach_research:
        if run_research:
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
        else:
            research_context = {
                "query": normalized,
                "status": "bypassed",
                "reason": plan.selection_rationale["scientific_research"],
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

    # 3. Real-Time Live Web Intelligence
    web_context: dict[str, Any] = {}
    if attach_web:
        if run_web:
            try:
                from engine.search import SearchManager
                s_mgr = search_mgr if search_mgr is not None else SearchManager()
                s_resp = s_mgr.search(normalized, max_results=5)
                web_context = s_resp.to_dict()
            except Exception as exc:
                logger.warning("Web search failed during brief creation: %s", exc)
                web_context = {
                    "query": normalized,
                    "provider": "unknown",
                    "status": "unavailable",
                    "total_results": 0,
                    "results": [],
                    "conflicts_detected": [],
                    "retrieval_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "disclosure_note": f"Live search unavailable ({exc}). Proceeding with stored intelligence.",
                }
        else:
            web_context = {
                "query": normalized,
                "provider": "none",
                "status": "bypassed",
                "total_results": 0,
                "results": [],
                "conflicts_detected": [],
                "retrieval_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "disclosure_note": plan.selection_rationale["live_internet"],
            }

    # 4. Anti-Hallucination & Fact-Checking Engine
    validation_context: dict[str, Any] = {}
    if claims:
        try:
            from engine.fact_checker import FactChecker
            checker = fact_checker if fact_checker is not None else FactChecker()
            report = checker.validate_claims(claims, brief_id=normalized)
            validation_context = report.to_dict()
        except Exception as exc:
            logger.warning("Fact-checking failed during brief creation: %s", exc)
            validation_context = {
                "status": "error",
                "reason": f"Validation error: {exc}",
                "total_claims": len(claims),
            }

    # 5. Language, Dialect and Code-Switching Detection
    detected_lang = detect_language(normalized)
    resp_lang = "telugu" if detected_lang == "telugu" else "english"
    detected_dialect = identify_dialect(normalized)
    from engine.nlp import detect_code_switching
    cs_meta = detect_code_switching(normalized).to_dict()

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
        validation_context=validation_context,
        web_context=web_context,
        subsystem_plan=plan.to_dict(),
        query_language=detected_lang,
        response_language=resp_lang,
        dialect=detected_dialect,
        code_switching=cs_meta,
    )
    logger.info(
        "Created intelligence brief [topic=%s, human_review_required=%s, knowledge_records=%d, research_evidence=%d, web_results=%d, validated_claims=%d]",
        brief.topic,
        brief.human_review_required,
        len(knowledge_context.get("records", [])),
        research_context.get("total_evidence", 0),
        web_context.get("total_results", 0),
        len(validation_context.get("claims", [])),
    )
    return brief
