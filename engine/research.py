"""ANTARĀ Intelligence Engine - Module 3: Research Intelligence.

Provides a provider-independent research retrieval, evidence classification,
provenance preservation, and human review system for modern academic,
psychological, and scientific evidence.

Architectural Principles:
1. Ground Truth & Provenance: Every piece of evidence is bound to an accredited source.
2. Anti-Fabrication: Never fabricate papers, DOIs, authors, or empirical statistics.
3. Quad-Classification: Classifies evidence into Supporting, Contradicting, Contextual,
   and Inconclusive without prematurely declaring scientific consensus.
4. Human Supervision: Newly ingested research defaults to 'unreviewed'. Approval or
   rejection requires reviewer identity and substantive notes.
5. Tamper & Duplicate Immunity: Uses normalized DOI and metadata deduplication, backed
   by append-only audit tracking.
"""

from abc import ABC, abstractmethod
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

from engine.knowledge import DEFAULT_DB_PATH
from engine.orchestrator import AntaraError

logger = logging.getLogger(__name__)

VALID_RESEARCH_STATUSES: tuple[str, ...] = ("unreviewed", "approved", "rejected")
VALID_EVIDENCE_CLASSIFICATIONS: tuple[str, ...] = (
    "supporting",
    "contradicting",
    "contextual",
    "inconclusive",
)
VALID_EVIDENCE_STRENGTHS: tuple[str, ...] = (
    "high",
    "moderate",
    "low",
    "exploratory",
)


class ResearchError(AntaraError):
    """Base exception for Research Intelligence module errors."""


class DuplicateResearchError(ResearchError):
    """Raised when attempting to insert an already existing research paper."""


class InvalidEvidenceError(ResearchError):
    """Raised when evidence metadata or classification fails constraints."""


class SubstantiveReviewError(ResearchError):
    """Raised when reviewer identity or review notes are missing or insubstantial."""


class ProviderError(ResearchError):
    """Raised when an external research provider fails or times out."""


def normalize_doi(doi: str | None) -> str | None:
    """Normalize a DOI string by stripping URL prefixes, whitespace, and lowercasing.

    Args:
        doi: Raw DOI string or URL (e.g. 'https://doi.org/10.1037/0022-3514.73.5.1080').

    Returns:
        Normalized clean DOI (e.g. '10.1037/0022-3514.73.5.1080') or None.
    """
    if not doi:
        return None
    cleaned = doi.strip().lower()
    cleaned = re.sub(r"^https?://(dx\.)?doi\.org/", "", cleaned)
    cleaned = re.sub(r"^doi:\s*", "", cleaned)
    return cleaned if cleaned else None


def compute_research_hash(
    title: str,
    authors: str,
    year: int | None,
    doi: str | None,
    abstract: str | None,
) -> str:
    """Compute a deterministic SHA-256 fingerprint for a research source.

    Args:
        title: Title of publication.
        authors: Authors string.
        year: Publication year.
        doi: Normalized DOI.
        abstract: Article abstract.

    Returns:
        Hexadecimal SHA-256 digest string.
    """
    canonical = (
        f"{title.strip().casefold()}|{authors.strip().casefold()}|"
        f"{year or 0}|{normalize_doi(doi) or ''}|{(abstract or '').strip()}"
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResearchSourceDraft:
    """Unpersisted research source metadata ingested from a provider."""

    title: str
    authors: str
    journal: str | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    methodology: str | None = None
    study_population: str | None = None
    sample_size: int | None = None
    limitations: str | None = None
    rights_note: str | None = None
    provider: str = "manual"

    def to_dict(self) -> dict[str, Any]:
        """Convert draft to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class ResearchSource:
    """Persisted bibliographic and methodological metadata for an academic source."""

    id: int
    title: str
    authors: str
    journal: str | None
    year: int | None
    doi: str | None
    url: str | None
    abstract: str | None
    methodology: str | None
    study_population: str | None
    sample_size: int | None
    limitations: str | None
    verification_status: str
    rights_note: str | None
    content_hash: str
    created_at_utc: str
    updated_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        """Convert source to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class EvidenceRecord:
    """Specific empirical claim or finding extracted from a research source."""

    id: int
    source_id: int
    finding: str
    claim: str
    classification: str
    strength: str
    limitations: str | None
    review_status: str
    created_at_utc: str
    updated_at_utc: str
    source: ResearchSource | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert evidence record to dictionary."""
        data = asdict(self)
        if self.source:
            data["source"] = self.source.to_dict()
        return data


@dataclass(frozen=True)
class ResearchAuditRecord:
    """Append-only audit trail event for human review of sources and evidence."""

    id: int
    target_type: str
    target_id: int
    previous_status: str
    new_status: str
    reviewer: str
    notes: str
    reviewed_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        """Convert audit record to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class ResearchContext:
    """Structured research evidence context attached to an intelligence brief."""

    query: str
    status: str
    reason: str
    total_sources: int
    total_evidence: int
    sources: list[dict[str, Any]]
    evidence_by_classification: dict[str, list[dict[str, Any]]]
    evidence_gaps: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary."""
        return asdict(self)


class ResearchProvider(ABC):
    """Abstract interface for scientific and academic research providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of research data provider."""

    @abstractmethod
    def search(
        self,
        query: str,
        limit: int = 5,
        timeout: float = 10.0,
    ) -> list[ResearchSourceDraft]:
        """Search provider for research literature matching query.

        Args:
            query: Search string or keywords.
            limit: Maximum results to retrieve.
            timeout: Network timeout in seconds.

        Returns:
            List of ResearchSourceDraft objects.

        Raises:
            ProviderError: If search encounters network or response failures.
        """


class MockResearchProvider(ResearchProvider):
    """Deterministic in-memory research provider for testing and offline operation."""

    def __init__(
        self,
        fixtures: list[ResearchSourceDraft] | None = None,
        should_fail: bool = False,
        failure_message: str = "Simulated network timeout",
    ) -> None:
        """Initialize mock provider with fixtures or simulated failure modes."""
        self._fixtures = fixtures or []
        self._should_fail = should_fail
        self._failure_message = failure_message

    @property
    def provider_name(self) -> str:
        return "mock_provider"

    def search(
        self,
        query: str,
        limit: int = 5,
        timeout: float = 10.0,
    ) -> list[ResearchSourceDraft]:
        if self._should_fail:
            raise ProviderError(f"[{self.provider_name}] {self._failure_message}")

        q_lower = query.casefold()
        matches = [
            f for f in self._fixtures
            if q_lower in f.title.casefold()
            or (f.abstract and q_lower in f.abstract.casefold())
            or any(term in f.title.casefold() for term in q_lower.split())
        ]
        return matches[:limit]


class ResearchManager:
    """Database manager and orchestrator for academic sources and evidence classification."""

    def __init__(
        self,
        db_path: Path | str = DEFAULT_DB_PATH,
        providers: list[ResearchProvider] | None = None,
    ) -> None:
        """Initialize the research manager.

        Args:
            db_path: Path to SQLite database.
            providers: List of research providers to query.
        """
        self.db_path = Path(db_path)
        if self.db_path != Path(":memory:"):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.providers = providers or [MockResearchProvider()]
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Create a new SQLite connection with foreign keys enabled."""
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
        """Create normalized research tables, constraints, and indexes."""
        with self.connection() as conn:
            with conn:
                # Table: Research Sources
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS research_sources (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        authors TEXT NOT NULL,
                        journal TEXT,
                        year INTEGER,
                        doi TEXT,
                        url TEXT,
                        abstract TEXT,
                        methodology TEXT,
                        study_population TEXT,
                        sample_size INTEGER,
                        limitations TEXT,
                        verification_status TEXT NOT NULL CHECK (
                            verification_status IN ('unreviewed', 'approved', 'rejected')
                        ) DEFAULT 'unreviewed',
                        rights_note TEXT,
                        content_hash TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL
                    );
                    """
                )

                # Table: Evidence Records
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS research_evidence (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_id INTEGER NOT NULL,
                        finding TEXT NOT NULL,
                        claim TEXT NOT NULL,
                        classification TEXT NOT NULL CHECK (
                            classification IN ('supporting', 'contradicting', 'contextual', 'inconclusive')
                        ),
                        strength TEXT NOT NULL CHECK (
                            strength IN ('high', 'moderate', 'low', 'exploratory')
                        ) DEFAULT 'moderate',
                        limitations TEXT,
                        review_status TEXT NOT NULL CHECK (
                            review_status IN ('unreviewed', 'approved', 'rejected')
                        ) DEFAULT 'unreviewed',
                        created_at_utc TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL,
                        FOREIGN KEY (source_id) REFERENCES research_sources(id) ON DELETE CASCADE
                    );
                    """
                )

                # Table: Append-Only Research Audit
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS research_audit (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        target_type TEXT NOT NULL CHECK (target_type IN ('source', 'evidence')),
                        target_id INTEGER NOT NULL,
                        previous_status TEXT NOT NULL,
                        new_status TEXT NOT NULL,
                        reviewer TEXT NOT NULL,
                        notes TEXT NOT NULL,
                        reviewed_at_utc TEXT NOT NULL
                    );
                    """
                )

                # Indexes
                conn.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_research_doi ON research_sources(doi) "
                    "WHERE doi IS NOT NULL AND doi != '';"
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_research_title_year ON research_sources(title, year);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_research_status ON research_sources(verification_status);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_source ON research_evidence(source_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_classification ON research_evidence(classification);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_status ON research_evidence(review_status);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_research_audit ON research_audit(target_type, target_id);")

    def insert_source(self, draft: ResearchSourceDraft) -> int:
        """Insert a research source draft with duplicate detection.

        Enforces DOI and normalized metadata deduplication.

        Args:
            draft: ResearchSourceDraft to persist.

        Returns:
            Integer primary key ID of created source.

        Raises:
            DuplicateResearchError: If an identical DOI or title/author/year already exists.
            ValueError: If title or authors are empty.
        """
        if not draft.title or not draft.title.strip():
            raise ValueError("Research source title cannot be empty.")
        if not draft.authors or not draft.authors.strip():
            raise ValueError("Research source authors cannot be empty.")

        clean_doi = normalize_doi(draft.doi)
        clean_title = draft.title.strip()
        first_author = draft.authors.split(",")[0].strip().casefold()

        with self.connection() as conn:
            # 1. DOI duplicate check
            if clean_doi:
                existing_doi = conn.execute(
                    "SELECT id FROM research_sources WHERE doi = ?;",
                    (clean_doi,),
                ).fetchone()
                if existing_doi:
                    raise DuplicateResearchError(
                        f"Research source with DOI '{clean_doi}' already exists (ID {existing_doi['id']})."
                    )

            # 2. Metadata duplicate check: title and year
            existing_meta = conn.execute(
                "SELECT id, authors FROM research_sources WHERE LOWER(title) = LOWER(?) AND year IS ?;",
                (clean_title, draft.year),
            ).fetchall()
            for row in existing_meta:
                row_first_author = row["authors"].split(",")[0].strip().casefold()
                if row_first_author == first_author:
                    raise DuplicateResearchError(
                        f"Research source '{clean_title}' by {draft.authors} ({draft.year}) "
                        f"already exists (ID {row['id']})."
                    )

            content_hash = compute_research_hash(
                title=clean_title,
                authors=draft.authors,
                year=draft.year,
                doi=clean_doi,
                abstract=draft.abstract,
            )
            now_utc = datetime.now(timezone.utc).isoformat()
            initial_status = "unreviewed"

            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO research_sources (
                        title, authors, journal, year, doi, url, abstract,
                        methodology, study_population, sample_size, limitations,
                        verification_status, rights_note, content_hash,
                        created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        clean_title,
                        draft.authors.strip(),
                        draft.journal,
                        draft.year,
                        clean_doi,
                        draft.url,
                        draft.abstract,
                        draft.methodology,
                        draft.study_population,
                        draft.sample_size,
                        draft.limitations,
                        initial_status,
                        draft.rights_note,
                        content_hash,
                        now_utc,
                        now_utc,
                    ),
                )
                source_id = int(cursor.lastrowid)

                conn.execute(
                    """
                    INSERT INTO research_audit (
                        target_type, target_id, previous_status, new_status,
                        reviewer, notes, reviewed_at_utc
                    ) VALUES ('source', ?, 'none', ?, 'SYSTEM:INGESTION',
                              'Ingested from provider; awaiting human review.', ?);
                    """,
                    (source_id, initial_status, now_utc),
                )
                return source_id

    def get_source(self, source_id: int) -> ResearchSource | None:
        """Retrieve a research source by primary key ID."""
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM research_sources WHERE id = ?;", (source_id,)).fetchone()
            if not row:
                return None
            return self._row_to_source(row)

    def search_sources(
        self,
        query: str | None = None,
        approved_only: bool = False,
        limit: int = 20,
    ) -> list[ResearchSource]:
        """Search research sources with optional approved-only filtering."""
        sql = "SELECT * FROM research_sources WHERE 1=1"
        params: list[Any] = []

        if approved_only:
            sql += " AND verification_status = 'approved'"
        if query:
            q_pat = f"%{query}%"
            sql += " AND (title LIKE ? OR authors LIKE ? OR abstract LIKE ? OR journal LIKE ?)"
            params.extend([q_pat] * 4)

        sql += " ORDER BY year DESC, id DESC LIMIT ?"
        params.append(limit)

        with self.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_source(r) for r in rows]

    def add_evidence(
        self,
        source_id: int,
        finding: str,
        claim: str,
        classification: str,
        strength: str = "moderate",
        limitations: str | None = None,
    ) -> int:
        """Classify and store an empirical finding linked to a research source.

        Args:
            source_id: Foreign key to research_sources.
            finding: Empirical observation or extracted result.
            claim: Specific hypothesis or statement supported/challenged.
            classification: One of 'supporting', 'contradicting', 'contextual', 'inconclusive'.
            strength: One of 'high', 'moderate', 'low', 'exploratory'.
            limitations: Known methodological constraints.

        Returns:
            Integer primary key ID of created evidence item.

        Raises:
            ValueError: If finding or claim is empty.
            InvalidEvidenceError: If classification or strength is invalid.
        """
        if not finding or not finding.strip():
            raise ValueError("Evidence finding cannot be empty.")
        if not claim or not claim.strip():
            raise ValueError("Evidence claim cannot be empty.")
        if classification not in VALID_EVIDENCE_CLASSIFICATIONS:
            raise InvalidEvidenceError(
                f"Invalid classification '{classification}'. Must be one of {VALID_EVIDENCE_CLASSIFICATIONS}."
            )
        if strength not in VALID_EVIDENCE_STRENGTHS:
            raise InvalidEvidenceError(
                f"Invalid strength '{strength}'. Must be one of {VALID_EVIDENCE_STRENGTHS}."
            )

        with self.connection() as conn:
            # Verify source exists
            src = conn.execute("SELECT id FROM research_sources WHERE id = ?;", (source_id,)).fetchone()
            if not src:
                raise ValueError(f"Research source with ID {source_id} does not exist.")

            now_utc = datetime.now(timezone.utc).isoformat()
            initial_status = "unreviewed"

            with conn:
                cursor = conn.execute(
                    """
                    INSERT INTO research_evidence (
                        source_id, finding, claim, classification, strength,
                        limitations, review_status, created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        source_id,
                        finding.strip(),
                        claim.strip(),
                        classification,
                        strength,
                        limitations,
                        initial_status,
                        now_utc,
                        now_utc,
                    ),
                )
                evidence_id = int(cursor.lastrowid)

                conn.execute(
                    """
                    INSERT INTO research_audit (
                        target_type, target_id, previous_status, new_status,
                        reviewer, notes, reviewed_at_utc
                    ) VALUES ('evidence', ?, 'none', ?, 'SYSTEM:EXTRACTION',
                              'Evidence classified; awaiting human review.', ?);
                    """,
                    (evidence_id, initial_status, now_utc),
                )
                return evidence_id

    def get_evidence(self, evidence_id: int) -> EvidenceRecord | None:
        """Retrieve an evidence record by ID, including its joined source metadata."""
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT e.*,
                       s.id AS s_id, s.title AS s_title, s.authors AS s_authors,
                       s.journal AS s_journal, s.year AS s_year, s.doi AS s_doi,
                       s.url AS s_url, s.abstract AS s_abstract, s.methodology AS s_methodology,
                       s.study_population AS s_study_population, s.sample_size AS s_sample_size,
                       s.limitations AS s_limitations, s.verification_status AS s_verification_status,
                       s.rights_note AS s_rights_note, s.content_hash AS s_content_hash,
                       s.created_at_utc AS s_created_at_utc, s.updated_at_utc AS s_updated_at_utc
                FROM research_evidence e
                JOIN research_sources s ON e.source_id = s.id
                WHERE e.id = ?;
                """,
                (evidence_id,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_evidence(row)

    def search_evidence(
        self,
        query: str | None = None,
        classification: str | None = None,
        approved_only: bool = False,
        limit: int = 20,
    ) -> list[EvidenceRecord]:
        """Search evidence items with classification and approval filters."""
        sql = """
            SELECT e.*,
                   s.id AS s_id, s.title AS s_title, s.authors AS s_authors,
                   s.journal AS s_journal, s.year AS s_year, s.doi AS s_doi,
                   s.url AS s_url, s.abstract AS s_abstract, s.methodology AS s_methodology,
                   s.study_population AS s_study_population, s.sample_size AS s_sample_size,
                   s.limitations AS s_limitations, s.verification_status AS s_verification_status,
                   s.rights_note AS s_rights_note, s.content_hash AS s_content_hash,
                   s.created_at_utc AS s_created_at_utc, s.updated_at_utc AS s_updated_at_utc
            FROM research_evidence e
            JOIN research_sources s ON e.source_id = s.id
            WHERE 1=1
        """
        params: list[Any] = []

        if approved_only:
            sql += " AND e.review_status = 'approved'"
        if classification:
            sql += " AND e.classification = ?"
            params.append(classification)
        if query:
            q_pat = f"%{query}%"
            sql += " AND (e.finding LIKE ? OR e.claim LIKE ? OR s.title LIKE ?)"
            params.extend([q_pat] * 3)

        sql += " ORDER BY e.id DESC LIMIT ?"
        params.append(limit)

        with self.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_evidence(r) for r in rows]

    def review_source(
        self,
        source_id: int,
        decision: str,
        reviewer: str,
        notes: str,
    ) -> ResearchAuditRecord:
        """Record a human review decision for a research source."""
        if decision not in VALID_RESEARCH_STATUSES:
            raise ValueError(f"Invalid decision '{decision}'. Must be one of {VALID_RESEARCH_STATUSES}.")
        if not reviewer or not reviewer.strip():
            raise SubstantiveReviewError("Reviewer identity cannot be empty.")
        if not notes or len(notes.strip()) < 15:
            raise SubstantiveReviewError("Review notes must be substantive (at least 15 characters).")

        with self.connection() as conn:
            current = conn.execute("SELECT * FROM research_sources WHERE id = ?;", (source_id,)).fetchone()
            if not current:
                raise ValueError(f"Research source with ID {source_id} not found.")

            previous_status = current["verification_status"]
            now_utc = datetime.now(timezone.utc).isoformat()

            with conn:
                conn.execute(
                    "UPDATE research_sources SET verification_status = ?, updated_at_utc = ? WHERE id = ?;",
                    (decision, now_utc, source_id),
                )
                cursor = conn.execute(
                    """
                    INSERT INTO research_audit (
                        target_type, target_id, previous_status, new_status,
                        reviewer, notes, reviewed_at_utc
                    ) VALUES ('source', ?, ?, ?, ?, ?, ?);
                    """,
                    (source_id, previous_status, decision, reviewer.strip(), notes.strip(), now_utc),
                )
                return ResearchAuditRecord(
                    id=int(cursor.lastrowid),
                    target_type="source",
                    target_id=source_id,
                    previous_status=previous_status,
                    new_status=decision,
                    reviewer=reviewer.strip(),
                    notes=notes.strip(),
                    reviewed_at_utc=now_utc,
                )

    def review_evidence(
        self,
        evidence_id: int,
        decision: str,
        reviewer: str,
        notes: str,
    ) -> ResearchAuditRecord:
        """Record a human review decision for an extracted evidence finding."""
        if decision not in VALID_RESEARCH_STATUSES:
            raise ValueError(f"Invalid decision '{decision}'. Must be one of {VALID_RESEARCH_STATUSES}.")
        if not reviewer or not reviewer.strip():
            raise SubstantiveReviewError("Reviewer identity cannot be empty.")
        if not notes or len(notes.strip()) < 15:
            raise SubstantiveReviewError("Review notes must be substantive (at least 15 characters).")

        with self.connection() as conn:
            current = conn.execute("SELECT * FROM research_evidence WHERE id = ?;", (evidence_id,)).fetchone()
            if not current:
                raise ValueError(f"Research evidence with ID {evidence_id} not found.")

            previous_status = current["review_status"]
            now_utc = datetime.now(timezone.utc).isoformat()

            with conn:
                conn.execute(
                    "UPDATE research_evidence SET review_status = ?, updated_at_utc = ? WHERE id = ?;",
                    (decision, now_utc, evidence_id),
                )
                cursor = conn.execute(
                    """
                    INSERT INTO research_audit (
                        target_type, target_id, previous_status, new_status,
                        reviewer, notes, reviewed_at_utc
                    ) VALUES ('evidence', ?, ?, ?, ?, ?, ?);
                    """,
                    (evidence_id, previous_status, decision, reviewer.strip(), notes.strip(), now_utc),
                )
                return ResearchAuditRecord(
                    id=int(cursor.lastrowid),
                    target_type="evidence",
                    target_id=evidence_id,
                    previous_status=previous_status,
                    new_status=decision,
                    reviewer=reviewer.strip(),
                    notes=notes.strip(),
                    reviewed_at_utc=now_utc,
                )

    def get_audit_history(self, target_type: str, target_id: int) -> list[ResearchAuditRecord]:
        """Retrieve audit history for a target source or evidence record."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM research_audit
                WHERE target_type = ? AND target_id = ?
                ORDER BY id ASC;
                """,
                (target_type, target_id),
            ).fetchall()
            return [
                ResearchAuditRecord(
                    id=int(r["id"]),
                    target_type=r["target_type"],
                    target_id=int(r["target_id"]),
                    previous_status=r["previous_status"],
                    new_status=r["new_status"],
                    reviewer=r["reviewer"],
                    notes=r["notes"],
                    reviewed_at_utc=r["reviewed_at_utc"],
                )
                for r in rows
            ]

    def query_providers(self, query: str, limit: int = 5) -> list[ResearchSourceDraft]:
        """Query all registered research providers, deduplicating and handling failures gracefully."""
        all_drafts: list[ResearchSourceDraft] = []
        seen_identifiers: set[str] = set()

        for provider in self.providers:
            try:
                results = provider.search(query, limit=limit)
                for draft in results:
                    ident = normalize_doi(draft.doi) or draft.title.strip().casefold()
                    if ident not in seen_identifiers:
                        seen_identifiers.add(ident)
                        all_drafts.append(draft)
                        if len(all_drafts) >= limit:
                            break
            except Exception as exc:
                logger.warning("Provider '%s' failed: %s", provider.provider_name, exc)

        return all_drafts

    def collect_research_for_question(
        self,
        question: str,
        topic: str | None = None,
        approved_only: bool = False,
    ) -> ResearchContext:
        """Gather relevant modern research evidence, classification, and gaps for a question."""
        raw_tokens = [t for t in re.findall(r"\b\w+\b", question.casefold()) if len(t) > 3]
        search_terms: list[str] = []
        for t in raw_tokens:
            if t not in search_terms:
                search_terms.append(t)
            for suffix in ("ation", "tion", "ing", "ion", "ed", "es", "ate", "s", "e"):
                if t.endswith(suffix) and len(t) - len(suffix) >= 4:
                    stem = t[:-len(suffix)]
                    if stem not in search_terms:
                        search_terms.append(stem)

        evidence_items: list[EvidenceRecord] = []
        seen_evidence_ids: set[int] = set()

        for term in search_terms:
            matches = self.search_evidence(query=term, approved_only=approved_only, limit=10)
            for m in matches:
                if m.id not in seen_evidence_ids:
                    seen_evidence_ids.add(m.id)
                    evidence_items.append(m)

        # Collect unique sources
        source_dict: dict[int, dict[str, Any]] = {}
        by_class: dict[str, list[dict[str, Any]]] = {
            "supporting": [],
            "contradicting": [],
            "contextual": [],
            "inconclusive": [],
        }

        for ev in evidence_items:
            by_class[ev.classification].append(ev.to_dict())
            if ev.source and ev.source.id not in source_dict:
                source_dict[ev.source.id] = ev.source.to_dict()

        evidence_gaps: list[str] = []
        if not evidence_items:
            evidence_gaps.append(
                "No empirical peer-reviewed research findings currently indexed for this query."
            )
        if not by_class["contradicting"]:
            evidence_gaps.append(
                "Countervailing or contradicting empirical studies have not yet been curated."
            )

        status = "research_collected" if evidence_items else "no_research_found"
        reason = (
            f"Collected {len(evidence_items)} evidence findings across {len(source_dict)} source(s)."
            if evidence_items
            else "No matching empirical research findings in database."
        )

        return ResearchContext(
            query=question,
            status=status,
            reason=reason,
            total_sources=len(source_dict),
            total_evidence=len(evidence_items),
            sources=list(source_dict.values()),
            evidence_by_classification=by_class,
            evidence_gaps=evidence_gaps,
        )

    def _row_to_source(self, row: sqlite3.Row) -> ResearchSource:
        """Convert a database row into a ResearchSource dataclass."""
        return ResearchSource(
            id=int(row["id"]),
            title=row["title"],
            authors=row["authors"],
            journal=row["journal"],
            year=row["year"],
            doi=row["doi"],
            url=row["url"],
            abstract=row["abstract"],
            methodology=row["methodology"],
            study_population=row["study_population"],
            sample_size=row["sample_size"],
            limitations=row["limitations"],
            verification_status=row["verification_status"],
            rights_note=row["rights_note"],
            content_hash=row["content_hash"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
        )

    def _row_to_evidence(self, row: sqlite3.Row) -> EvidenceRecord:
        """Convert a joined database row into an EvidenceRecord dataclass."""
        source: ResearchSource | None = None
        if "s_id" in row.keys() and row["s_id"] is not None:
            source = ResearchSource(
                id=int(row["s_id"]),
                title=row["s_title"],
                authors=row["s_authors"],
                journal=row["s_journal"],
                year=row["s_year"],
                doi=row["s_doi"],
                url=row["s_url"],
                abstract=row["s_abstract"],
                methodology=row["s_methodology"],
                study_population=row["s_study_population"],
                sample_size=row["s_sample_size"],
                limitations=row["s_limitations"],
                verification_status=row["s_verification_status"],
                rights_note=row["s_rights_note"],
                content_hash=row["s_content_hash"],
                created_at_utc=row["s_created_at_utc"],
                updated_at_utc=row["s_updated_at_utc"],
            )

        return EvidenceRecord(
            id=int(row["id"]),
            source_id=int(row["source_id"]),
            finding=row["finding"],
            claim=row["claim"],
            classification=row["classification"],
            strength=row["strength"],
            limitations=row["limitations"],
            review_status=row["review_status"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
            source=source,
        )
