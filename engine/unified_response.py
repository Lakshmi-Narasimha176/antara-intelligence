"""ANTARĀ Intelligence Engine - Unified Response System.

Defines the comprehensive 12-dimensional unified response schema for Layer 1.
Consolidates direct answers, detailed explanations, traditional knowledge, modern research,
current live web intelligence, supporting & contradicting evidence, full source citations
(with URLs, publication dates, and retrieval timestamps), uncertainties, fact-checking,
and human governance status.
"""

from dataclasses import asdict, dataclass, field
import json
import logging
from typing import Any

from engine.orchestrator import IntelligenceBrief
from engine.reasoning import ReasoningAnalysis
from engine.search import classify_source_freshness

logger = logging.getLogger("antara.unified_response")


@dataclass(frozen=True)
class UnifiedCitation:
    """Standardized citation with source type, locators, URLs, and timestamps."""

    source_type: str  # 'gita', 'research', 'web'
    title: str
    source_id: str | int | None = None
    url: str | None = None
    author_or_source: str | None = None
    publication_date: str | None = None
    retrieval_timestamp_utc: str | None = None
    locator: str | None = None
    content_hash: str | None = None
    credibility_tier: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert citation to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class UnifiedResponse:
    """Consistent Layer 1 unified intelligence response schema.

    Contains all 12 core dimensions required by Layer 1 specification:
    1. direct_answer: Clear, concise direct summary.
    2. detailed_explanation: In-depth comparative analysis.
    3. traditional_perspective: Verified Indian knowledge (Bhagavad Gītā).
    4. scientific_perspective: Approved empirical & psychological research.
    5. current_developments: Real-time web intelligence and recent findings.
    6. supporting_evidence: Consolidated supporting findings across sources.
    7. contradicting_evidence: Conflicting evidence, boundary conditions, or opposing views.
    8. source_citations: Full citations with URLs, publication dates, and retrieval timestamps.
    9. uncertainty_and_limitations: Epistemic caveats, study limitations, and research gaps.
    10. fact_checking_results: Deterministic Module 4 anti-hallucination validation audit.
    11. human_review_status: Human-in-the-loop governance review and approval tracking.
    12. report_id and timestamps for provenance and auditability.
    """

    report_id: str
    question: str
    direct_answer: str
    detailed_explanation: str
    traditional_perspective: dict[str, Any]
    scientific_perspective: dict[str, Any]
    current_developments: dict[str, Any]
    supporting_evidence: list[dict[str, Any]]
    contradicting_evidence: list[dict[str, Any]]
    source_citations: list[dict[str, Any]]
    uncertainty_and_limitations: list[str]
    fact_checking_results: dict[str, Any]
    human_review_status: dict[str, Any]
    created_at_utc: str
    updated_at_utc: str
    governance_status: str = "pending_review"
    language_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert unified response to dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize unified response to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def build_unified_response(
    brief: IntelligenceBrief,
    analysis: ReasoningAnalysis,
    governance_record: dict[str, Any] | None = None,
) -> UnifiedResponse:
    """Construct a complete UnifiedResponse from an IntelligenceBrief and ReasoningAnalysis.

    Args:
        brief: Populated IntelligenceBrief from the orchestrator.
        analysis: Validated ReasoningAnalysis from the reasoning engine.
        governance_record: Optional governance record dictionary from Module 5.

    Returns:
        UnifiedResponse instance.
    """
    # 1. Direct answer and detailed explanation
    direct_ans = analysis.executive_summary or "Analysis synthesized from authenticated sources."
    detailed_exp = analysis.critical_analysis or analysis.original_synthesized_insight

    # 2. Traditional perspective (Bhagavad Gita)
    trad_citations: list[dict[str, Any]] = []
    trad_records = brief.knowledge_context.get("records", [])
    for rec in trad_records:
        src = rec.get("source") or {}
        trad_citations.append({
            "source_type": "gita",
            "source_id": rec.get("record_id") or rec.get("id"),
            "title": src.get("title", "Bhagavad Gītā"),
            "author_or_source": src.get("author") or src.get("translator"),
            "locator": f"Chapter {rec.get('chapter')}, Verse {rec.get('verse')} ({rec.get('locator') or 'N/A'})",
            "url": src.get("url"),
            "publication_date": str(src.get("year")) if src.get("year") else None,
            "retrieval_timestamp_utc": None,
            "content_hash": rec.get("content_hash"),
            "credibility_tier": "canonical_scripture",
        })

    traditional_perspective = {
        "status": brief.knowledge_context.get("status", "completed"),
        "reason": brief.knowledge_context.get("reason"),
        "framework": analysis.philosophical_perspective,
        "teachings": analysis.relevant_gita_teachings,
        "citations": trad_citations,
    }

    # 3. Scientific perspective (Empirical Research)
    sci_citations: list[dict[str, Any]] = []
    sci_sources = brief.research_context.get("sources", [])
    for s in sci_sources:
        sci_citations.append({
            "source_type": "research",
            "source_id": s.get("id"),
            "title": s.get("title", ""),
            "author_or_source": s.get("authors", ""),
            "locator": f"DOI: {s.get('doi')}" if s.get("doi") else f"Journal: {s.get('journal')}",
            "url": s.get("url") or (f"https://doi.org/{s.get('doi')}" if s.get("doi") else None),
            "publication_date": str(s.get("year")) if s.get("year") else None,
            "retrieval_timestamp_utc": None,
            "content_hash": s.get("content_hash"),
            "credibility_tier": "peer_reviewed_academic",
        })

    scientific_perspective = {
        "status": brief.research_context.get("status", "completed"),
        "reason": brief.research_context.get("reason"),
        "framework": analysis.modern_scientific_perspectives,
        "supporting_findings": analysis.supporting_research_evidence,
        "contradicting_findings": analysis.contradicting_research_evidence,
        "citations": sci_citations,
    }

    # 4. Current developments (Real-Time Web Intelligence)
    web_citations: list[dict[str, Any]] = []
    current_sources: list[dict[str, Any]] = []
    web_results = brief.web_context.get("results", [])
    for w in web_results:
        freshness_status, freshness_disclosure = classify_source_freshness(
            w.get("published_date"),
            w.get("retrieved_at_utc"),
        )
        web_citations.append({
            "source_type": "web",
            "source_id": w.get("url"),
            "title": w.get("title", ""),
            "author_or_source": w.get("source_domain", ""),
            "locator": w.get("source_domain", ""),
            "url": w.get("url"),
            "publication_date": w.get("published_date"),
            "retrieval_timestamp_utc": w.get("retrieved_at_utc"),
            "content_hash": w.get("content_hash"),
            "credibility_tier": w.get("credibility_tier", "general"),
            "freshness_status": freshness_status,
            "freshness_disclosure": freshness_disclosure,
        })
        current_sources.append({
            "title": w.get("title"),
            "url": w.get("url"),
            "domain": w.get("source_domain"),
            "credibility_tier": w.get("credibility_tier"),
            "published_date": w.get("published_date"),
            "retrieved_at_utc": w.get("retrieved_at_utc"),
            "snippet": w.get("snippet"),
            "freshness_status": freshness_status,
            "freshness_disclosure": freshness_disclosure,
        })

    current_developments = {
        "status": brief.web_context.get("status", "bypassed"),
        "provider": brief.web_context.get("provider", "none"),
        "total_results": brief.web_context.get("total_results", 0),
        "disclosure_note": brief.web_context.get("disclosure_note", ""),
        "sources": current_sources,
        "conflicts_detected": brief.web_context.get("conflicts_detected", []),
        "citations": web_citations,
    }

    # 5. Consolidated Supporting Evidence
    supporting_evidence: list[dict[str, Any]] = []
    for g in analysis.relevant_gita_teachings:
        supporting_evidence.append({
            "type": "traditional_scripture",
            "source": f"Bhagavad Gītā Ch {g.get('chapter')}, V {g.get('verse')}",
            "finding": g.get("teaching"),
            "exact_quote": g.get("translation_quote") or g.get("sanskrit_quote"),
        })
    for ev in analysis.supporting_research_evidence:
        supporting_evidence.append({
            "type": "empirical_science",
            "source_id": ev.get("source_id"),
            "evidence_id": ev.get("evidence_id"),
            "finding": ev.get("finding"),
        })

    # 6. Consolidated Contradicting Evidence & Nuance
    contradicting_evidence: list[dict[str, Any]] = []
    for ev in analysis.contradicting_research_evidence:
        contradicting_evidence.append({
            "type": "empirical_science_conflict",
            "source_id": ev.get("source_id"),
            "evidence_id": ev.get("evidence_id"),
            "finding": ev.get("finding"),
        })
    # Include approved contradicting empirical findings directly from research context
    for ev in brief.research_context.get("evidence_by_classification", {}).get("contradicting", []):
        ev_id = ev.get("id") or ev.get("evidence_id")
        if not any(c.get("evidence_id") == ev_id for c in contradicting_evidence):
            contradicting_evidence.append({
                "type": "empirical_science_contradiction",
                "source_id": ev.get("source_id"),
                "evidence_id": ev_id,
                "claim": ev.get("claim"),
                "finding": ev.get("finding"),
            })
    for conf in brief.web_context.get("conflicts_detected", []):
        contradicting_evidence.append({
            "type": "live_web_conflict",
            "conflict_type": conf.get("type"),
            "note": conf.get("note"),
            "source_1": conf.get("source_1"),
            "source_2": conf.get("source_2"),
        })

    # 7. Unified source citations list
    all_citations = trad_citations + sci_citations + web_citations

    # 8. Uncertainty and limitations
    limitations: list[str] = list(analysis.limitations_and_uncertainty)
    limitations.extend(analysis.research_gaps)
    for gap in brief.research_context.get("evidence_gaps", []):
        if gap not in limitations:
            limitations.append(gap)

    # 9. Human review & governance status
    gov_status = (
        governance_record.get("status")
        if governance_record
        else analysis.status
    )
    human_review_status = {
        "status": gov_status,
        "human_review_required": True,
        "validation_passed": (analysis.status != "validation_failed"),
        "reviewer": (governance_record.get("reviewer") if governance_record else None),
        "review_notes": (governance_record.get("review_notes") if governance_record else None),
        "approved_hash": (governance_record.get("approved_hash") if governance_record else None),
        "audit_trail": analysis.review_audit,
    }

    # 10. Language foundation metadata
    lang_metadata = {
        "query_language": getattr(brief, "query_language", "unknown"),
        "response_language": getattr(brief, "response_language", "english"),
        "dialect": getattr(brief, "dialect", None),
        "code_switching": getattr(brief, "code_switching", None),
    }

    return UnifiedResponse(
        report_id=analysis.report_id,
        question=brief.question,
        direct_answer=direct_ans,
        detailed_explanation=detailed_exp,
        traditional_perspective=traditional_perspective,
        scientific_perspective=scientific_perspective,
        current_developments=current_developments,
        supporting_evidence=supporting_evidence,
        contradicting_evidence=contradicting_evidence,
        source_citations=all_citations,
        uncertainty_and_limitations=limitations,
        fact_checking_results=analysis.validation_report,
        human_review_status=human_review_status,
        created_at_utc=analysis.created_at_utc,
        updated_at_utc=analysis.updated_at_utc,
        governance_status=gov_status,
        language_metadata=lang_metadata,
    )
