"""ANTARĀ Intelligence Engine - AI Reasoning Engine.

Combines authenticated Bhagavad Gītā knowledge and approved modern scientific/psychological
research into structured, 16-dimensional philosophical-scientific intelligence syntheses.

Strict Anti-Hallucination & Governance Invariants:
1. Never claim that modern science "proves" the Bhagavad Gītā.
2. Only reference supplied, authenticated source and evidence identifiers.
3. Every generated report is deterministically validated by Module 4 before review.
4. Validation failures prevent reports from entering the approval workflow.
5. Mandatory human review: status moves through generated -> pending_review -> approved/rejected.
"""

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
import sqlite3
from typing import Any, Generator

from engine.context_builder import ContextBuilder, FormattedContext
from engine.fact_checker import (
    FactChecker,
    Claim,
)
from engine.knowledge import DEFAULT_DB_PATH, validate_substantive_evidence
from engine.llm_provider import LLMMessage, LLMProvider, MockLLMProvider
from engine.orchestrator import AntaraError, IntelligenceBrief

logger = logging.getLogger("antara.reasoning")

# Controlled Lifecycle States
STATE_GENERATED = "generated"
STATE_VALIDATION_FAILED = "validation_failed"
STATE_PENDING_REVIEW = "pending_review"
STATE_APPROVED = "approved"
STATE_REJECTED = "rejected"

VALID_REASONING_STATES = frozenset({
    STATE_GENERATED,
    STATE_VALIDATION_FAILED,
    STATE_PENDING_REVIEW,
    STATE_APPROVED,
    STATE_REJECTED,
})

FORBIDDEN_PROOFS_PATTERNS = [
    re.compile(r"\bscience\s+proves\s+(the\s+)?(bhagavad\s+)?g[iī]t[aā]\b", re.IGNORECASE),
    re.compile(r"\b(bhagavad\s+)?g[iī]t[aā]\s+(is\s+)?(empirically\s+|scientifically\s+)?proven\s+by\s+science\b", re.IGNORECASE),
    re.compile(r"\bmodern\s+physics\s+proves\s+(vedanta|gita)\b", re.IGNORECASE),
]


class ReasoningEngineError(AntaraError):
    """Base exception for AI reasoning engine errors."""


class ReasoningWorkflowError(ReasoningEngineError):
    """Raised when an illegal state transition is attempted."""


class ReasoningValidationError(ReasoningEngineError):
    """Raised when structured LLM output violates schema requirements."""


SYSTEM_REASONING_PROMPT = """You are the ANTARĀ AI Reasoning Engine, an evidence-grounded philosophical and cognitive synthesis system.
Your mission is to produce rigorous, structured analysis comparing authenticated Bhagavad Gītā teachings with approved modern scientific and psychological evidence.

MANDATORY RULES & INVARIANTS:
1. EPISTEMOLOGICAL INDEPENDENCE: Never claim that modern science "proves" the Bhagavad Gītā, or that the Gītā "anticipated" modern physics/neuroscience. Treat them as distinct epistemological frameworks with distinct methodologies, truth criteria, and ontologies.
2. ZERO CITATION FABRICATION: You may ONLY cite the explicit GITA_VERSE_ID and RESEARCH_EVIDENCE_ID numbers provided in the context block. Never invent verse numbers, chapter numbers, authors, sample sizes, or DOIs.
3. QUOTATIONS VS. PARAPHRASES: Direct quotations must match the supplied text verbatim. Paraphrases must be marked accurately.
4. BALANCED CRITIQUE: You must explicitly present both supporting AND contradicting evidence, identifying real methodological differences and philosophical tensions.
5. STRICT JSON OUTPUT: Return ONLY a valid JSON object containing the exact 16 required fields.

REQUIRED JSON FIELDS:
{
  "executive_summary": "High-level synthesis (2-3 sentences)",
  "philosophical_perspective": "Systematic Bhagavad Gītā philosophical framework",
  "relevant_gita_teachings": [
    {
      "verse_id": 1,
      "chapter": 2,
      "verse": 47,
      "teaching": "Specific philosophical principle",
      "sanskrit_quote": "Exact Sanskrit text or null",
      "translation_quote": "Exact translation or null"
    }
  ],
  "modern_scientific_perspectives": "Contemporary psychological / cognitive framework",
  "supporting_research_evidence": [
    {
      "evidence_id": 1,
      "source_id": 1,
      "finding": "Specific empirical finding"
    }
  ],
  "contradicting_research_evidence": [
    {
      "evidence_id": 2,
      "source_id": 1,
      "finding": "Specific conflicting finding or boundary condition"
    }
  ],
  "philosophical_and_scientific_similarities": ["Similarity 1", "..."],
  "important_differences": ["Difference 1", "..."],
  "critical_analysis": "Deep comparative evaluation of epistemology and methodology",
  "original_synthesized_insight": "Novel synthesis respecting boundaries of both traditions",
  "practical_implications": ["Actionable guidance 1", "..."],
  "limitations_and_uncertainty": ["Methodological caveat 1", "..."],
  "research_gaps": ["Unresolved empirical question 1", "..."],
  "exact_source_citations": [
    {"type": "gita", "id": 1, "locator": "Ch 2, V 47"},
    {"type": "research", "id": 1, "doi": "10.1037/0033-2909.133.1.65"}
  ],
  "claims_requiring_human_review": [
    {
      "claim_id": "c1",
      "claim_text": "Precise factual or interpretive statement",
      "source_type": "gita",
      "record_id": 1,
      "chapter": 2,
      "verse": 47,
      "is_direct_quote": true,
      "quoted_text": "Exact quote text",
      "quote_field": "translation"
    }
  ]
}
"""


@dataclass(frozen=True)
class ReasoningAnalysis:
    """Complete 16-dimensional philosophical-scientific reasoning output."""

    report_id: str
    question: str
    executive_summary: str
    philosophical_perspective: str
    relevant_gita_teachings: list[dict[str, Any]]
    modern_scientific_perspectives: str
    supporting_research_evidence: list[dict[str, Any]]
    contradicting_research_evidence: list[dict[str, Any]]
    philosophical_and_scientific_similarities: list[str]
    important_differences: list[str]
    critical_analysis: str
    original_synthesized_insight: str
    practical_implications: list[str]
    limitations_and_uncertainty: list[str]
    research_gaps: list[str]
    exact_source_citations: list[dict[str, Any]]
    claims_requiring_human_review: list[dict[str, Any]]
    status: str
    human_review_required: bool
    created_at_utc: str
    updated_at_utc: str
    validation_report: dict[str, Any] = field(default_factory=dict)
    review_audit: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert reasoning analysis to dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize analysis to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class ReasoningEngine:
    """ANTARĀ AI Reasoning Engine coordinating context building, LLM synthesis, and validation."""

    def __init__(
        self,
        db_path: Path | str = DEFAULT_DB_PATH,
        provider: LLMProvider | None = None,
        fact_checker: FactChecker | None = None,
    ) -> None:
        """Initialize ReasoningEngine with database, LLM provider, and Module 4 validator.

        Args:
            db_path: Path to runtime SQLite database.
            provider: LLMProvider instance. Defaults to MockLLMProvider.
            fact_checker: FactChecker instance.
        """
        self.db_path = Path(db_path)
        if self.db_path != Path(":memory:"):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.provider = provider if provider is not None else MockLLMProvider()
        self.fact_checker = fact_checker if fact_checker is not None else FactChecker(self.db_path)
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Create a new SQLite connection with foreign keys and Row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager guaranteeing connection closure on Windows."""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Create persistent reasoning tables and indexes."""
        with self.connection() as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reasoning_reports (
                        id TEXT PRIMARY KEY,
                        question TEXT NOT NULL,
                        status TEXT NOT NULL CHECK (
                            status IN ('generated', 'validation_failed', 'pending_review', 'approved', 'rejected')
                        ),
                        content_json TEXT NOT NULL,
                        validation_status TEXT,
                        human_review_required INTEGER NOT NULL DEFAULT 1,
                        created_at_utc TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reasoning_audit (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        report_id TEXT NOT NULL REFERENCES reasoning_reports(id) ON DELETE CASCADE,
                        previous_status TEXT NOT NULL,
                        new_status TEXT NOT NULL,
                        reviewer TEXT NOT NULL,
                        notes TEXT NOT NULL,
                        reviewed_at_utc TEXT NOT NULL
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_reasoning_status ON reasoning_reports(status);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_reasoning_audit ON reasoning_audit(report_id);")

    def analyze_brief(self, brief: IntelligenceBrief) -> ReasoningAnalysis:
        """Execute end-to-end reasoning synthesis on an IntelligenceBrief."""
        # 1. Build bounded, provenance-preserving context
        builder = ContextBuilder(brief)
        context = builder.build()

        # 2. Query LLM Provider with strict JSON contract
        user_prompt = f"Please synthesize structured analysis for the inquiry:\n\n{context.prompt_context_text}"
        messages = [
            LLMMessage(role="system", content=SYSTEM_REASONING_PROMPT),
            LLMMessage(role="user", content=user_prompt),
        ]

        llm_response = self.provider.generate(messages, json_mode=True, temperature=0.2)
        raw_data = llm_response.raw_json
        if not raw_data:
            try:
                raw_data = json.loads(llm_response.content)
            except Exception as exc:
                logger.error("Failed to parse reasoning JSON from provider: %s", exc)
                raise ReasoningValidationError("Provider output could not be parsed as valid JSON.") from exc

        # 3. Check for forbidden proof assertions
        full_text_corpus = f"{llm_response.content} {raw_data.get('critical_analysis', '')} {raw_data.get('original_synthesized_insight', '')}"
        forbidden_proof_detected = any(pattern.search(full_text_corpus) for pattern in FORBIDDEN_PROOFS_PATTERNS)

        # 4. Extract and normalize claims for Module 4 verification
        claims_to_validate, fabricated_ids_detected = self._extract_claims_for_validation(raw_data, context)

        # 5. Execute Module 4 Anti-Hallucination & Fact-Checking
        report_id = f"reason_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{hashlib.sha256(brief.question.encode()).hexdigest()[:8]}"
        fact_report = self.fact_checker.validate_claims(claims_to_validate, brief_id=report_id)

        # 6. Determine controlled report state
        # Invariants:
        # - Any fabricated ID, forbidden proof claim, or Module 4 failure -> validation_failed
        # - Passing validation -> pending_review
        # - No report can automatically enter approved
        now_utc = datetime.now(timezone.utc).isoformat()
        if fabricated_ids_detected or forbidden_proof_detected:
            status = STATE_VALIDATION_FAILED
        elif fact_report.integrity_failures:
            status = STATE_VALIDATION_FAILED
        elif fact_report.overall_status in ("FAILED_UNSUPPORTED", "FAILED_CONTRADICTED", "INTEGRITY_COMPROMISED"):
            status = STATE_VALIDATION_FAILED
        else:
            status = STATE_PENDING_REVIEW

        analysis = ReasoningAnalysis(
            report_id=report_id,
            question=brief.question,
            executive_summary=raw_data.get("executive_summary", ""),
            philosophical_perspective=raw_data.get("philosophical_perspective", ""),
            relevant_gita_teachings=raw_data.get("relevant_gita_teachings", []),
            modern_scientific_perspectives=raw_data.get("modern_scientific_perspectives", ""),
            supporting_research_evidence=raw_data.get("supporting_research_evidence", []),
            contradicting_research_evidence=raw_data.get("contradicting_research_evidence", []),
            philosophical_and_scientific_similarities=raw_data.get("philosophical_and_scientific_similarities", []),
            important_differences=raw_data.get("important_differences", []),
            critical_analysis=raw_data.get("critical_analysis", ""),
            original_synthesized_insight=raw_data.get("original_synthesized_insight", ""),
            practical_implications=raw_data.get("practical_implications", []),
            limitations_and_uncertainty=raw_data.get("limitations_and_uncertainty", []),
            research_gaps=raw_data.get("research_gaps", []),
            exact_source_citations=raw_data.get("exact_source_citations", []),
            claims_requiring_human_review=raw_data.get("claims_requiring_human_review", []),
            status=status,
            human_review_required=True,
            created_at_utc=now_utc,
            updated_at_utc=now_utc,
            validation_report=fact_report.to_dict(),
            review_audit=[],
        )

        # Persist to SQLite
        self._persist_report(analysis)
        return analysis

    def _extract_claims_for_validation(
        self,
        raw_data: dict[str, Any],
        context: FormattedContext,
    ) -> tuple[list[Claim], bool]:
        """Extract structured claims from LLM output and check against allowed context identifiers."""
        claims: list[Claim] = []
        fabricated_ids_detected = False

        # Extract explicit claims
        raw_claims = raw_data.get("claims_requiring_human_review", [])
        for idx, item in enumerate(raw_claims, start=1):
            if isinstance(item, dict):
                # Verify record_id if provided
                src_type = item.get("source_type", "none")
                rec_id = item.get("record_id")
                if rec_id is not None:
                    try:
                        rec_id_int = int(rec_id)
                        if src_type == "gita" and rec_id_int not in context.allowed_gita_ids:
                            fabricated_ids_detected = True
                        elif src_type == "research" and rec_id_int not in context.allowed_evidence_ids:
                            fabricated_ids_detected = True
                    except (ValueError, TypeError):
                        fabricated_ids_detected = True

                claims.append(
                    Claim(
                        claim_id=str(item.get("claim_id") or f"gen_claim_{idx}"),
                        claim_text=str(item.get("claim_text") or item.get("claim", "")),
                        claim_type=item.get("claim_type", "general"),
                        source_type=src_type,
                        record_id=rec_id,
                        chapter=item.get("chapter"),
                        verse=item.get("verse"),
                        quoted_text=item.get("quoted_text"),
                        quote_field=item.get("quote_field"),
                        is_direct_quote=bool(item.get("is_direct_quote", False)),
                    )
                )

        # Extract Gita teachings as claims if explicit claims list was empty
        if not claims:
            for idx, g_item in enumerate(raw_data.get("relevant_gita_teachings", []), start=1):
                v_id = g_item.get("verse_id")
                if v_id is not None and int(v_id) not in context.allowed_gita_ids:
                    fabricated_ids_detected = True

                q_text = g_item.get("translation_quote") or g_item.get("sanskrit_quote")
                claims.append(
                    Claim(
                        claim_id=f"gita_teaching_{idx}",
                        claim_text=g_item.get("teaching", ""),
                        claim_type="gita_quotation" if q_text else "gita_paraphrase",
                        source_type="gita",
                        record_id=v_id,
                        chapter=g_item.get("chapter"),
                        verse=g_item.get("verse"),
                        quoted_text=q_text,
                        quote_field="translation" if g_item.get("translation_quote") else "sanskrit",
                        is_direct_quote=bool(q_text),
                    )
                )

        return claims, fabricated_ids_detected

    def _persist_report(self, analysis: ReasoningAnalysis) -> None:
        """Persist a ReasoningAnalysis record to the SQLite database."""
        with self.connection() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO reasoning_reports (
                        id, question, status, content_json, validation_status,
                        human_review_required, created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        status = excluded.status,
                        content_json = excluded.content_json,
                        validation_status = excluded.validation_status,
                        updated_at_utc = excluded.updated_at_utc;
                    """,
                    (
                        analysis.report_id,
                        analysis.question,
                        analysis.status,
                        analysis.to_json(),
                        analysis.validation_report.get("overall_status"),
                        1 if analysis.human_review_required else 0,
                        analysis.created_at_utc,
                        analysis.updated_at_utc,
                    ),
                )

    def review_report(
        self,
        report_id: str,
        decision: str,
        reviewer: str,
        notes: str,
    ) -> ReasoningAnalysis:
        """Record a human review decision (approved or rejected) on a reasoning report.

        Args:
            report_id: Unique identifier of the report.
            decision: Target state ('approved' or 'rejected').
            reviewer: Name and scholarly affiliation of human reviewer.
            notes: Substantive review rationale (minimum 15 characters).

        Returns:
            Updated ReasoningAnalysis instance.

        Raises:
            ReasoningWorkflowError: If transitioning an unvalidated or illegal report state.
            SubstantiveEvidenceError: If notes are insubstantial or empty.
        """
        clean_decision = decision.strip().lower()
        if clean_decision not in (STATE_APPROVED, STATE_REJECTED):
            raise ReasoningWorkflowError(f"Decision must be 'approved' or 'rejected', got '{decision}'.")

        clean_notes = validate_substantive_evidence(notes)
        if not reviewer or not reviewer.strip():
            raise ReasoningWorkflowError("Reviewer identity cannot be empty.")

        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM reasoning_reports WHERE id = ?;", (report_id,)
            ).fetchone()
            if not row:
                raise ReasoningWorkflowError(f"Reasoning report '{report_id}' not found.")

            current_status = row["status"]

            # Workflow Invariant: Only pending_review can be approved
            if clean_decision == STATE_APPROVED and current_status != STATE_PENDING_REVIEW:
                raise ReasoningWorkflowError(
                    f"Cannot approve report in state '{current_status}'. "
                    f"Only reports that have passed Module 4 validation (state: '{STATE_PENDING_REVIEW}') can be approved."
                )

            data = json.loads(row["content_json"])
            now_utc = datetime.now(timezone.utc).isoformat()

            audit_entry = {
                "report_id": report_id,
                "previous_status": current_status,
                "new_status": clean_decision,
                "reviewer": reviewer.strip(),
                "notes": clean_notes,
                "reviewed_at_utc": now_utc,
            }

            with conn:
                conn.execute(
                    """
                    INSERT INTO reasoning_audit (report_id, previous_status, new_status, reviewer, notes, reviewed_at_utc)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (report_id, current_status, clean_decision, reviewer.strip(), clean_notes, now_utc),
                )
                conn.execute(
                    """
                    UPDATE reasoning_reports
                    SET status = ?, updated_at_utc = ?
                    WHERE id = ?;
                    """,
                    (clean_decision, now_utc, report_id),
                )

            data["status"] = clean_decision
            data["updated_at_utc"] = now_utc
            data.setdefault("review_audit", []).append(audit_entry)

            # Update cached JSON
            with conn:
                conn.execute(
                    "UPDATE reasoning_reports SET content_json = ? WHERE id = ?;",
                    (json.dumps(data, ensure_ascii=False), report_id),
                )

            return ReasoningAnalysis(**data)

    def get_report(self, report_id: str) -> ReasoningAnalysis:
        """Fetch a persisted reasoning report by ID."""
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM reasoning_reports WHERE id = ?;", (report_id,)).fetchone()
            if not row:
                raise ReasoningWorkflowError(f"Reasoning report '{report_id}' not found.")
            data = json.loads(row["content_json"])
            return ReasoningAnalysis(**data)
