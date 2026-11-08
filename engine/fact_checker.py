"""ANTARĀ Intelligence Engine - Module 4: Anti-Hallucination & Fact-Checking Engine.

Provides deterministic, evidence-grounded validation of claims, quotations,
source references, and citations against authenticated primary knowledge (Bhagavad Gītā)
and approved modern scientific/empirical research evidence.

Core Invariants:
1. Never invent sources, quotations, translations, or empirical findings.
2. Never treat an LLM as an authority for factual verification.
3. Distinguish mechanical integrity (SHA-256 hashes, existence checks) from scholarly/scientific validity.
4. Distinguish verbatim quotations from paraphrases.
5. Explicitly detect and preserve contradictions rather than suppressing them.
6. Strictly enforce human supervision: human_review_required is always True.
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

from engine.knowledge import DEFAULT_DB_PATH, compute_content_hash
from engine.orchestrator import AntaraError
from engine.research import compute_research_hash, normalize_doi

logger = logging.getLogger("antara.fact_checker")

# Validation Status Constants
STATUS_SOURCE_VERIFIED = "source_verified"
STATUS_PARTIALLY_SUPPORTED = "partially_supported"
STATUS_UNSUPPORTED = "unsupported"
STATUS_CONTRADICTED = "contradicted"
STATUS_INSUFFICIENT_EVIDENCE = "insufficient_evidence"
STATUS_REQUIRES_HUMAN_REVIEW = "requires_human_review"

VALID_CLAIM_STATUSES = frozenset({
    STATUS_SOURCE_VERIFIED,
    STATUS_PARTIALLY_SUPPORTED,
    STATUS_UNSUPPORTED,
    STATUS_CONTRADICTED,
    STATUS_INSUFFICIENT_EVIDENCE,
    STATUS_REQUIRES_HUMAN_REVIEW,
})

VALID_CLAIM_TYPES = frozenset({
    "gita_quotation",
    "gita_paraphrase",
    "gita_interpretation",
    "research_finding",
    "research_claim",
    "interpretive_claim",
    "general",
})

VALID_SOURCE_TYPES = frozenset({
    "gita",
    "research",
    "none",
})


class FactCheckerError(AntaraError):
    """Base exception for all fact-checking engine errors."""


class ClaimValidationError(FactCheckerError):
    """Raised when an input claim schema or field is malformed."""


class IntegrityFailureError(FactCheckerError):
    """Raised or flagged when cryptographic content hash does not match source text."""


@dataclass(frozen=True)
class Claim:
    """A discrete claim, quotation, finding, or interpretation to be fact-checked."""

    claim_id: str
    claim_text: str
    claim_type: str = "general"
    source_type: str = "none"  # 'gita', 'research', 'none'
    source_id: int | None = None
    record_id: int | None = None  # verse_id or evidence_id
    chapter: int | None = None
    verse: int | None = None
    quoted_text: str | None = None
    quote_field: str | None = None  # 'sanskrit', 'transliteration', 'translation', 'finding', 'abstract'
    citation_locator: str | None = None
    doi: str | None = None
    url: str | None = None
    is_direct_quote: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert claim to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Claim":
        """Construct and validate a Claim instance from a dictionary."""
        if not isinstance(data, dict):
            raise ClaimValidationError(f"Claim data must be a dict, got {type(data).__name__}")

        raw_id = data.get("claim_id")
        if not raw_id or not str(raw_id).strip():
            raise ClaimValidationError("Claim missing required non-empty 'claim_id'.")

        raw_text = data.get("claim_text")
        if not raw_text or not str(raw_text).strip():
            raise ClaimValidationError("Claim missing required non-empty 'claim_text'.")

        source_type = data.get("source_type", "none")
        if source_type not in VALID_SOURCE_TYPES:
            raise ClaimValidationError(
                f"Invalid source_type '{source_type}'. Allowed: {sorted(VALID_SOURCE_TYPES)}"
            )

        claim_type = data.get("claim_type", "general")
        if claim_type not in VALID_CLAIM_TYPES:
            raise ClaimValidationError(
                f"Invalid claim_type '{claim_type}'. Allowed: {sorted(VALID_CLAIM_TYPES)}"
            )

        # Validate chapter / verse ranges if present
        chapter = data.get("chapter")
        if chapter is not None:
            try:
                chapter = int(chapter)
                if not (1 <= chapter <= 18):
                    raise ClaimValidationError(f"Bhagavad Gita chapter must be 1-18, got {chapter}.")
            except (ValueError, TypeError) as exc:
                raise ClaimValidationError(f"Invalid chapter value: {chapter}") from exc

        verse = data.get("verse")
        if verse is not None:
            try:
                verse = int(verse)
                if verse < 1:
                    raise ClaimValidationError(f"Verse number must be >= 1, got {verse}.")
            except (ValueError, TypeError) as exc:
                raise ClaimValidationError(f"Invalid verse value: {verse}") from exc

        return cls(
            claim_id=str(raw_id).strip(),
            claim_text=str(raw_text).strip(),
            claim_type=claim_type,
            source_type=source_type,
            source_id=int(data["source_id"]) if data.get("source_id") is not None else None,
            record_id=int(data["record_id"]) if data.get("record_id") is not None else None,
            chapter=chapter,
            verse=verse,
            quoted_text=str(data["quoted_text"]) if data.get("quoted_text") is not None else None,
            quote_field=str(data["quote_field"]).strip().lower() if data.get("quote_field") else None,
            citation_locator=data.get("citation_locator"),
            doi=str(data["doi"]).strip() if data.get("doi") else None,
            url=str(data["url"]).strip() if data.get("url") else None,
            is_direct_quote=bool(data.get("is_direct_quote", False)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class ClaimValidationResult:
    """Deterministic validation result for an individual claim."""

    claim_id: str
    claim_text: str
    status: str
    reasons: list[str]
    source_exists: bool
    source_verified: bool
    integrity_valid: bool
    is_direct_quote: bool
    quote_matches: bool | None
    referenced_source_id: int | None
    referenced_record_id: int | None
    supporting_evidence_ids: list[int]
    contradicting_evidence_ids: list[int]
    flags: list[str]
    human_review_required: bool
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class FactCheckReport:
    """Comprehensive fact-checking and validation report."""

    report_id: str
    brief_id: str
    timestamp_utc: str
    overall_status: str
    total_claims: int
    verified_claims: int
    partially_supported_claims: int
    unsupported_claims: int
    contradicted_claims: int
    insufficient_evidence_claims: int
    requires_human_review_claims: int
    claims: list[dict[str, Any]]
    supporting_sources: list[dict[str, Any]]
    contradicting_sources: list[dict[str, Any]]
    missing_citations: list[str]
    integrity_failures: list[dict[str, Any]]
    unresolved_questions: list[str]
    human_review_required: bool
    summary_notes: str

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to UTF-8 formatted JSON."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class FactChecker:
    """Deterministic, evidence-grounded anti-hallucination validation engine."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        """Initialize FactChecker with SQLite database path.

        Args:
            db_path: Path to runtime SQLite database.
        """
        self.db_path = Path(db_path)

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection | None, None, None]:
        """Context manager yielding SQLite connection with foreign keys and Row factory."""
        if not self.db_path.exists():
            logger.warning("FactChecker database does not exist at '%s'", self.db_path)
            yield None
            return

        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            yield conn
        except sqlite3.Error as exc:
            logger.error("FactChecker connection error for '%s': %s", self.db_path, exc)
            yield None
        finally:
            if conn:
                conn.close()

    def validate_claim(self, claim: Claim) -> ClaimValidationResult:
        """Validate a single claim against authenticated sources and approved evidence.

        Args:
            claim: Claim instance to evaluate.

        Returns:
            ClaimValidationResult with deterministic status, flags, and reasons.
        """
        if claim.source_type == "none":
            return self._validate_unlinked_claim(claim)
        elif claim.source_type == "gita":
            return self._validate_gita_claim(claim)
        elif claim.source_type == "research":
            return self._validate_research_claim(claim)
        else:
            return ClaimValidationResult(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                status=STATUS_UNSUPPORTED,
                reasons=[f"Unrecognized source_type: '{claim.source_type}'"],
                source_exists=False,
                source_verified=False,
                integrity_valid=True,
                is_direct_quote=claim.is_direct_quote,
                quote_matches=None,
                referenced_source_id=None,
                referenced_record_id=None,
                supporting_evidence_ids=[],
                contradicting_evidence_ids=[],
                flags=["invalid_source_type"],
                human_review_required=True,
            )

    def _validate_unlinked_claim(self, claim: Claim) -> ClaimValidationResult:
        """Validate a claim presented without an explicit source citation."""
        flags: list[str] = ["missing_citation"]
        reasons: list[str] = []

        if claim.claim_type in ("gita_quotation", "gita_paraphrase"):
            reasons.append("Claim references Bhagavad Gītā knowledge without citing any verse or source.")
            status = STATUS_UNSUPPORTED
        elif claim.claim_type in ("research_finding", "research_claim"):
            reasons.append("Claim asserts an empirical or scientific finding without citing any research source or DOI.")
            status = STATUS_UNSUPPORTED
        elif claim.claim_type == "interpretive_claim":
            reasons.append("Interpretive claim provided without grounding citations; requires human review.")
            status = STATUS_REQUIRES_HUMAN_REVIEW
            flags.append("unsupported_interpretation")
        else:
            reasons.append("Claim has no source citation or evidence attached.")
            status = STATUS_UNSUPPORTED

        return ClaimValidationResult(
            claim_id=claim.claim_id,
            claim_text=claim.claim_text,
            status=status,
            reasons=reasons,
            source_exists=False,
            source_verified=False,
            integrity_valid=True,
            is_direct_quote=claim.is_direct_quote,
            quote_matches=None,
            referenced_source_id=None,
            referenced_record_id=None,
            supporting_evidence_ids=[],
            contradicting_evidence_ids=[],
            flags=flags,
            human_review_required=True,
        )

    def _validate_gita_claim(self, claim: Claim) -> ClaimValidationResult:
        """Validate a Bhagavad Gītā claim or quotation against authenticated verses."""
        with self.connection() as conn:
            if conn is None:
                return ClaimValidationResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    status=STATUS_UNSUPPORTED,
                    reasons=["Knowledge repository is unavailable or database file not found."],
                    source_exists=False,
                    source_verified=False,
                    integrity_valid=False,
                    is_direct_quote=claim.is_direct_quote,
                    quote_matches=None,
                    referenced_source_id=claim.source_id,
                    referenced_record_id=claim.record_id,
                    supporting_evidence_ids=[],
                    contradicting_evidence_ids=[],
                    flags=["database_unavailable"],
                    human_review_required=True,
                )

            # 1. Fetch verse record
            verse_row: sqlite3.Row | None = None
            if claim.record_id is not None:
                verse_row = conn.execute(
                    "SELECT * FROM verses WHERE id = ?;", (claim.record_id,)
                ).fetchone()
            elif claim.chapter is not None and claim.verse is not None:
                if claim.source_id is not None:
                    verse_row = conn.execute(
                        "SELECT * FROM verses WHERE source_id = ? AND chapter = ? AND verse = ?;",
                        (claim.source_id, claim.chapter, claim.verse),
                    ).fetchone()
                else:
                    verse_row = conn.execute(
                        "SELECT * FROM verses WHERE chapter = ? AND verse = ? ORDER BY id ASC LIMIT 1;",
                        (claim.chapter, claim.verse),
                    ).fetchone()

            if verse_row is None:
                locator = f"Ch {claim.chapter}, V {claim.verse}" if claim.chapter else f"ID {claim.record_id}"
                return ClaimValidationResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    status=STATUS_UNSUPPORTED,
                    reasons=[f"Referenced Bhagavad Gītā verse ({locator}) does not exist in repository."],
                    source_exists=False,
                    source_verified=False,
                    integrity_valid=True,
                    is_direct_quote=claim.is_direct_quote,
                    quote_matches=None,
                    referenced_source_id=claim.source_id,
                    referenced_record_id=claim.record_id,
                    supporting_evidence_ids=[],
                    contradicting_evidence_ids=[],
                    flags=["nonexistent_source_reference"],
                    human_review_required=True,
                )

            # 2. Cryptographic content hash check (defense-in-depth against database tampering)
            computed_hash = compute_content_hash(
                chapter=int(verse_row["chapter"]),
                verse=int(verse_row["verse"]),
                sanskrit=verse_row["sanskrit"],
                transliteration=verse_row["transliteration"],
                translation=verse_row["translation"],
                language=verse_row["language"],
            )
            stored_hash = verse_row["content_hash"]
            integrity_valid = computed_hash == stored_hash

            flags: list[str] = []
            reasons: list[str] = []
            details: dict[str, Any] = {
                "chapter": int(verse_row["chapter"]),
                "verse": int(verse_row["verse"]),
                "verification_status": verse_row["verification_status"],
            }

            if not integrity_valid:
                flags.append("tampered_record")
                reasons.append(
                    f"Cryptographic hash mismatch on verse {verse_row['id']}. Stored text differs from recorded hash."
                )
                details["computed_hash"] = computed_hash
                details["stored_hash"] = stored_hash
                return ClaimValidationResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    status=STATUS_REQUIRES_HUMAN_REVIEW,
                    reasons=reasons,
                    source_exists=True,
                    source_verified=False,
                    integrity_valid=False,
                    is_direct_quote=claim.is_direct_quote,
                    quote_matches=None,
                    referenced_source_id=int(verse_row["source_id"]),
                    referenced_record_id=int(verse_row["id"]),
                    supporting_evidence_ids=[],
                    contradicting_evidence_ids=[],
                    flags=flags,
                    human_review_required=True,
                    details=details,
                )

            # 3. Check scholarly verification status
            v_status = verse_row["verification_status"]
            source_verified = v_status == "verified"

            if v_status == "rejected":
                flags.append("rejected_source")
                reasons.append(
                    f"Referenced verse {verse_row['id']} was explicitly rejected during scholarly review."
                )
                return ClaimValidationResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    status=STATUS_UNSUPPORTED,
                    reasons=reasons,
                    source_exists=True,
                    source_verified=False,
                    integrity_valid=True,
                    is_direct_quote=claim.is_direct_quote,
                    quote_matches=None,
                    referenced_source_id=int(verse_row["source_id"]),
                    referenced_record_id=int(verse_row["id"]),
                    supporting_evidence_ids=[],
                    contradicting_evidence_ids=[],
                    flags=flags,
                    human_review_required=True,
                    details=details,
                )
            elif v_status == "unreviewed":
                flags.append("unreviewed_source")
                reasons.append(
                    f"Referenced verse {verse_row['id']} is unreviewed and not authenticated by human scholarship."
                )

            # 4. Check Quotation or Paraphrase Matching
            quote_matches: bool | None = None
            if claim.is_direct_quote or claim.quoted_text:
                q_text = (claim.quoted_text or claim.claim_text).strip()
                match_field = claim.quote_field

                target_text = ""
                if match_field == "sanskrit":
                    target_text = verse_row["sanskrit"]
                elif match_field == "transliteration":
                    target_text = verse_row["transliteration"]
                elif match_field == "translation":
                    target_text = verse_row["translation"]
                else:
                    # Search across all three canonical fields
                    target_text = f"{verse_row['sanskrit']} {verse_row['transliteration']} {verse_row['translation']}"

                # Compare normalized whitespace
                clean_q = " ".join(q_text.split())
                clean_target = " ".join(target_text.split())

                if clean_q == clean_target or clean_q.casefold() in clean_target.casefold():
                    quote_matches = True
                    if source_verified:
                        status = STATUS_SOURCE_VERIFIED
                        reasons.append("Direct quotation exactly verified against authenticated verse.")
                    else:
                        status = STATUS_REQUIRES_HUMAN_REVIEW
                else:
                    quote_matches = False
                    status = STATUS_UNSUPPORTED
                    flags.append("mismatched_quotation")
                    reasons.append(
                        f"Direct quotation does not match stored text in verse {verse_row['id']} ({match_field or 'all fields'})."
                    )
            else:
                # Claim is a paraphrase or conceptual assertion
                quote_matches = None
                if claim.claim_type == "gita_paraphrase":
                    flags.append("paraphrase_requires_human_assessment")
                    if source_verified:
                        status = STATUS_PARTIALLY_SUPPORTED
                        reasons.append(
                            "Referenced verse is verified, but claim is a paraphrase requiring human assessment for philological faithfulness."
                        )
                    else:
                        status = STATUS_REQUIRES_HUMAN_REVIEW
                        reasons.append("Paraphrase references an unreviewed verse; requires human review.")
                elif claim.claim_type == "gita_interpretation":
                    flags.append("interpretation_requires_human_review")
                    status = STATUS_REQUIRES_HUMAN_REVIEW
                    reasons.append(
                        "Philosophical interpretation cannot be certified mechanically as factual; requires human scholarly review."
                    )
                else:
                    status = STATUS_SOURCE_VERIFIED if source_verified else STATUS_REQUIRES_HUMAN_REVIEW
                    reasons.append("Claim references authenticated verse record.")

            return ClaimValidationResult(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                status=status,
                reasons=reasons,
                source_exists=True,
                source_verified=source_verified,
                integrity_valid=True,
                is_direct_quote=claim.is_direct_quote,
                quote_matches=quote_matches,
                referenced_source_id=int(verse_row["source_id"]),
                referenced_record_id=int(verse_row["id"]),
                supporting_evidence_ids=[],
                contradicting_evidence_ids=[],
                flags=flags,
                human_review_required=True,
                details=details,
            )

    def _validate_research_claim(self, claim: Claim) -> ClaimValidationResult:
        """Validate an academic research finding, claim, or citation against approved evidence."""
        with self.connection() as conn:
            if conn is None:
                return ClaimValidationResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    status=STATUS_UNSUPPORTED,
                    reasons=["Research repository is unavailable or database file not found."],
                    source_exists=False,
                    source_verified=False,
                    integrity_valid=False,
                    is_direct_quote=claim.is_direct_quote,
                    quote_matches=None,
                    referenced_source_id=claim.source_id,
                    referenced_record_id=claim.record_id,
                    supporting_evidence_ids=[],
                    contradicting_evidence_ids=[],
                    flags=["database_unavailable"],
                    human_review_required=True,
                )

            # 1. Fetch research evidence or source record
            evidence_row: sqlite3.Row | None = None
            source_row: sqlite3.Row | None = None

            if claim.record_id is not None:
                evidence_row = conn.execute(
                    "SELECT * FROM research_evidence WHERE id = ?;", (claim.record_id,)
                ).fetchone()
                if evidence_row:
                    source_row = conn.execute(
                        "SELECT * FROM research_sources WHERE id = ?;", (evidence_row["source_id"],)
                    ).fetchone()
            elif claim.source_id is not None:
                source_row = conn.execute(
                    "SELECT * FROM research_sources WHERE id = ?;", (claim.source_id,)
                ).fetchone()
            elif claim.doi:
                clean_doi = normalize_doi(claim.doi)
                source_row = conn.execute(
                    "SELECT * FROM research_sources WHERE doi = ?;", (clean_doi,)
                ).fetchone()

            if source_row is None and evidence_row is None:
                return ClaimValidationResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    status=STATUS_UNSUPPORTED,
                    reasons=["Referenced research source or evidence record not found in repository."],
                    source_exists=False,
                    source_verified=False,
                    integrity_valid=True,
                    is_direct_quote=claim.is_direct_quote,
                    quote_matches=None,
                    referenced_source_id=claim.source_id,
                    referenced_record_id=claim.record_id,
                    supporting_evidence_ids=[],
                    contradicting_evidence_ids=[],
                    flags=["nonexistent_source_reference"],
                    human_review_required=True,
                )

            flags: list[str] = []
            reasons: list[str] = []
            supporting_ids: list[int] = []
            contradicting_ids: list[int] = []
            details: dict[str, Any] = {}

            # 2. Check Parent Source Verification Status
            src_status = source_row["verification_status"] if source_row else "unreviewed"
            if src_status == "rejected":
                flags.append("rejected_source")
                reasons.append(
                    f"Parent research source (ID {source_row['id']}) was rejected during peer/human review."
                )
                return ClaimValidationResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    status=STATUS_UNSUPPORTED,
                    reasons=reasons,
                    source_exists=True,
                    source_verified=False,
                    integrity_valid=True,
                    is_direct_quote=claim.is_direct_quote,
                    quote_matches=None,
                    referenced_source_id=int(source_row["id"]) if source_row else None,
                    referenced_record_id=int(evidence_row["id"]) if evidence_row else None,
                    supporting_evidence_ids=[],
                    contradicting_evidence_ids=[],
                    flags=flags,
                    human_review_required=True,
                    details={"source_status": src_status},
                )
            elif src_status == "unreviewed":
                flags.append("unreviewed_source")
                reasons.append(
                    f"Parent research source (ID {source_row['id']}) is unreviewed and not yet approved."
                )

            # Check DOI consistency if provided
            if claim.doi and source_row and source_row["doi"]:
                clean_claim_doi = normalize_doi(claim.doi)
                if clean_claim_doi != source_row["doi"]:
                    flags.append("mismatched_doi")
                    reasons.append(
                        f"Claim DOI '{clean_claim_doi}' does not match stored source DOI '{source_row['doi']}'."
                    )

            # 3. Check Evidence Record Status & Strength
            if evidence_row:
                ev_id = int(evidence_row["id"])
                ev_status = evidence_row["review_status"]
                ev_strength = evidence_row["strength"]
                ev_class = evidence_row["classification"]
                details["evidence_id"] = ev_id
                details["review_status"] = ev_status
                details["strength"] = ev_strength
                details["classification"] = ev_class

                if ev_status == "approved":
                    supporting_ids.append(ev_id)
                elif ev_status == "rejected":
                    flags.append("rejected_evidence")
                    reasons.append(f"Referenced empirical evidence (ID {ev_id}) was rejected in review.")
                    return ClaimValidationResult(
                        claim_id=claim.claim_id,
                        claim_text=claim.claim_text,
                        status=STATUS_UNSUPPORTED,
                        reasons=reasons,
                        source_exists=True,
                        source_verified=False,
                        integrity_valid=True,
                        is_direct_quote=claim.is_direct_quote,
                        quote_matches=None,
                        referenced_source_id=int(source_row["id"]) if source_row else None,
                        referenced_record_id=ev_id,
                        supporting_evidence_ids=[],
                        contradicting_evidence_ids=[],
                        flags=flags,
                        human_review_required=True,
                        details=details,
                    )
                elif ev_status == "unreviewed":
                    flags.append("unreviewed_evidence")
                    reasons.append(
                        f"Referenced empirical evidence (ID {ev_id}) is unreviewed; lacks human approval."
                    )

                if ev_strength in ("low", "exploratory"):
                    flags.append("low_strength_evidence")
                    reasons.append(
                        f"Evidence has low/exploratory strength ('{ev_strength}'); insufficient for standalone verification."
                    )

            # 4. Contradiction Detection
            # Look for approved contradicting evidence records linked to this source or topic keywords
            source_id_val = int(source_row["id"]) if source_row else (int(evidence_row["source_id"]) if evidence_row else 0)
            contra_rows = conn.execute(
                """
                SELECT id, finding, claim, review_status FROM research_evidence
                WHERE source_id = ? AND classification = 'contradicting' AND review_status = 'approved';
                """,
                (source_id_val,),
            ).fetchall()

            for crow in contra_rows:
                contradicting_ids.append(int(crow["id"]))

            if contradicting_ids:
                flags.append("explicit_contradiction_detected")
                reasons.append(
                    f"Direct conflicting empirical evidence found: approved contradicting records {contradicting_ids}."
                )

            # 5. Check Quotation or Paraphrase Matching
            quote_matches: bool | None = None
            if claim.is_direct_quote or claim.quoted_text:
                q_text = (claim.quoted_text or claim.claim_text).strip()
                target_corpus = ""
                if evidence_row:
                    target_corpus = f"{evidence_row['finding']} {evidence_row['claim']}"
                elif source_row:
                    target_corpus = f"{source_row['abstract'] or ''} {source_row['title']}"

                clean_q = " ".join(q_text.split())
                clean_target = " ".join(target_corpus.split())

                if clean_q == clean_target or clean_q.casefold() in clean_target.casefold():
                    quote_matches = True
                else:
                    quote_matches = False
                    flags.append("mismatched_quotation")
                    reasons.append("Direct quotation does not match stored empirical findings or abstract.")

            # 6. Status Determination
            source_verified = (
                source_row is not None
                and src_status == "approved"
                and (evidence_row is None or evidence_row["review_status"] == "approved")
            )

            if contradicting_ids:
                status = STATUS_CONTRADICTED
            elif "mismatched_quotation" in flags or "mismatched_doi" in flags:
                status = STATUS_UNSUPPORTED
            elif "unreviewed_source" in flags or "unreviewed_evidence" in flags or "low_strength_evidence" in flags:
                status = STATUS_INSUFFICIENT_EVIDENCE
            elif not claim.is_direct_quote:
                # Paraphrase or empirical synthesis
                if source_row and source_row["limitations"]:
                    flags.append("methodological_limitations_noted")
                    status = STATUS_PARTIALLY_SUPPORTED
                    reasons.append(
                        f"Evidence approved, but source notes limitations: {source_row['limitations']}"
                    )
                elif source_verified:
                    status = STATUS_SOURCE_VERIFIED
                    reasons.append("Claim accurately aligns with approved empirical research evidence.")
                else:
                    status = STATUS_PARTIALLY_SUPPORTED
            else:
                # Direct quote that matched
                if quote_matches and source_verified:
                    status = STATUS_SOURCE_VERIFIED
                    reasons.append("Direct quotation verified against approved empirical finding.")
                else:
                    status = STATUS_REQUIRES_HUMAN_REVIEW

            return ClaimValidationResult(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                status=status,
                reasons=reasons,
                source_exists=True,
                source_verified=source_verified,
                integrity_valid=True,
                is_direct_quote=claim.is_direct_quote,
                quote_matches=quote_matches,
                referenced_source_id=int(source_row["id"]) if source_row else None,
                referenced_record_id=int(evidence_row["id"]) if evidence_row else None,
                supporting_evidence_ids=supporting_ids,
                contradicting_evidence_ids=contradicting_ids,
                flags=flags,
                human_review_required=True,
                details=details,
            )

    def validate_claims(
        self,
        claims: list[Claim | dict[str, Any]],
        brief_id: str = "brief_auto",
    ) -> FactCheckReport:
        """Validate a collection of claims and compile an immutable validation report.

        Args:
            claims: List of Claim instances or raw dictionaries.
            brief_id: Identifier of the associated research brief.

        Returns:
            FactCheckReport containing deterministic outcomes and audit details.
        """
        report_id = f"fc_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{hashlib.sha256(brief_id.encode()).hexdigest()[:8]}"
        now_utc = datetime.now(timezone.utc).isoformat()

        if not claims:
            return FactCheckReport(
                report_id=report_id,
                brief_id=brief_id,
                timestamp_utc=now_utc,
                overall_status="NO_CLAIMS_EVALUATED",
                total_claims=0,
                verified_claims=0,
                partially_supported_claims=0,
                unsupported_claims=0,
                contradicted_claims=0,
                insufficient_evidence_claims=0,
                requires_human_review_claims=0,
                claims=[],
                supporting_sources=[],
                contradicting_sources=[],
                missing_citations=[],
                integrity_failures=[],
                unresolved_questions=["No claims were provided for factual validation."],
                human_review_required=True,
                summary_notes="Empty claims collection evaluated.",
            )

        validated_claims: list[ClaimValidationResult] = []
        missing_citations: list[str] = []
        integrity_failures: list[dict[str, Any]] = []
        supporting_source_map: dict[str, dict[str, Any]] = {}
        contradicting_source_map: dict[str, dict[str, Any]] = {}
        unresolved_questions: list[str] = []

        v_count = 0
        ps_count = 0
        u_count = 0
        c_count = 0
        ie_count = 0
        rhr_count = 0

        with self.connection() as conn:
            for raw_claim in claims:
                claim_obj = raw_claim if isinstance(raw_claim, Claim) else Claim.from_dict(raw_claim)
                res = self.validate_claim(claim_obj)
                validated_claims.append(res)

                if res.status == STATUS_SOURCE_VERIFIED:
                    v_count += 1
                elif res.status == STATUS_PARTIALLY_SUPPORTED:
                    ps_count += 1
                elif res.status == STATUS_UNSUPPORTED:
                    u_count += 1
                elif res.status == STATUS_CONTRADICTED:
                    c_count += 1
                elif res.status == STATUS_INSUFFICIENT_EVIDENCE:
                    ie_count += 1
                elif res.status == STATUS_REQUIRES_HUMAN_REVIEW:
                    rhr_count += 1

                if "missing_citation" in res.flags:
                    missing_citations.append(res.claim_id)

                if "tampered_record" in res.flags:
                    integrity_failures.append({
                        "claim_id": res.claim_id,
                        "record_id": res.referenced_record_id,
                        "details": res.details,
                    })

                if "explicit_contradiction_detected" in res.flags:
                    unresolved_questions.append(
                        f"Claim '{res.claim_id}' is contradicted by approved evidence IDs {res.contradicting_evidence_ids}."
                    )

                # Fetch source descriptors for provenance lists
                if conn and res.referenced_source_id:
                    if claim_obj.source_type == "gita":
                        srow = conn.execute("SELECT * FROM sources WHERE id = ?;", (res.referenced_source_id,)).fetchone()
                        if srow:
                            skey = f"gita_{srow['id']}"
                            if res.source_verified and skey not in supporting_source_map:
                                supporting_source_map[skey] = {
                                    "type": "gita",
                                    "id": int(srow["id"]),
                                    "title": srow["title"],
                                    "author": srow["author"],
                                    "locator": claim_obj.citation_locator,
                                }
                    elif claim_obj.source_type == "research":
                        srow = conn.execute("SELECT * FROM research_sources WHERE id = ?;", (res.referenced_source_id,)).fetchone()
                        if srow:
                            skey = f"research_{srow['id']}"
                            if res.status == STATUS_CONTRADICTED and skey not in contradicting_source_map:
                                contradicting_source_map[skey] = {
                                    "type": "research",
                                    "id": int(srow["id"]),
                                    "title": srow["title"],
                                    "authors": srow["authors"],
                                    "doi": srow["doi"],
                                    "year": srow["year"],
                                }
                            elif res.source_verified and skey not in supporting_source_map:
                                supporting_source_map[skey] = {
                                    "type": "research",
                                    "id": int(srow["id"]),
                                    "title": srow["title"],
                                    "authors": srow["authors"],
                                    "doi": srow["doi"],
                                    "year": srow["year"],
                                }

        # Determine overall validation outcome
        if integrity_failures:
            overall_status = "INTEGRITY_COMPROMISED"
        elif c_count > 0:
            overall_status = "FAILED_CONTRADICTED"
        elif u_count > 0:
            overall_status = "FAILED_UNSUPPORTED"
        elif ps_count > 0 or ie_count > 0 or rhr_count > 0:
            overall_status = "REQUIRES_HUMAN_REVIEW"
        elif v_count == len(claims):
            overall_status = "PASSED_VERIFIED"
        else:
            overall_status = "REQUIRES_HUMAN_REVIEW"

        summary_notes = (
            f"Validated {len(claims)} claim(s): {v_count} verified, {ps_count} partially supported, "
            f"{u_count} unsupported, {c_count} contradicted, {ie_count} insufficient evidence, "
            f"{rhr_count} requiring human review. Overall outcome: {overall_status}."
        )

        return FactCheckReport(
            report_id=report_id,
            brief_id=brief_id,
            timestamp_utc=now_utc,
            overall_status=overall_status,
            total_claims=len(claims),
            verified_claims=v_count,
            partially_supported_claims=ps_count,
            unsupported_claims=u_count,
            contradicted_claims=c_count,
            insufficient_evidence_claims=ie_count,
            requires_human_review_claims=rhr_count,
            claims=[c.to_dict() for c in validated_claims],
            supporting_sources=list(supporting_source_map.values()),
            contradicting_sources=list(contradicting_source_map.values()),
            missing_citations=missing_citations,
            integrity_failures=integrity_failures,
            unresolved_questions=unresolved_questions,
            human_review_required=True,
            summary_notes=summary_notes,
        )


def validate_brief_claims(
    brief: Any,
    claims: list[Claim | dict[str, Any]] | None = None,
    fact_checker: FactChecker | None = None,
) -> FactCheckReport:
    """Validate claims in the context of an IntelligenceBrief.

    Args:
        brief: Populated IntelligenceBrief instance.
        claims: Optional list of explicit claims to evaluate.
        fact_checker: Optional FactChecker instance.

    Returns:
        FactCheckReport detailing validation findings and human review requirements.
    """
    checker = fact_checker if fact_checker is not None else FactChecker()
    brief_id = getattr(brief, "question", "unknown_brief")
    claim_list = claims or []
    return checker.validate_claims(claim_list, brief_id=brief_id)
