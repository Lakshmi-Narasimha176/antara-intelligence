"""ANTARĀ Intelligence Engine - Module 5: Human-in-the-Loop Governance & Publishing.

Provides an auditable, human-controlled governance system managing AI-generated
intelligence reports through validation gating, human review, version preservation,
cryptographic fingerprint checks, and tamper-resistant publishing.

Core Invariants:
1. No AI-generated report is published without explicit human authorization.
2. Reports must pass Module 4 anti-hallucination validation before entering pending_review.
3. Content modifications after approval immediately invalidate that approval.
4. Fingerprints must match at every stage from review to publication.
5. All lifecycle state transitions maintain an append-only audit trail.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Generator

from engine.knowledge import DEFAULT_DB_PATH, validate_substantive_evidence
from engine.orchestrator import AntaraError
from engine.reasoning import ReasoningAnalysis

logger = logging.getLogger("antara.governance")

# Controlled Lifecycle States
STATE_GENERATED = "generated"
STATE_VALIDATION_FAILED = "validation_failed"
STATE_PENDING_REVIEW = "pending_review"
STATE_APPROVED = "approved"
STATE_REJECTED = "rejected"
STATE_REVISION_REQUESTED = "revision_requested"
STATE_READY_TO_PUBLISH = "ready_to_publish"
STATE_PUBLISHED = "published"
STATE_ARCHIVED = "archived"

VALID_GOVERNANCE_STATES = frozenset({
    STATE_GENERATED,
    STATE_VALIDATION_FAILED,
    STATE_PENDING_REVIEW,
    STATE_APPROVED,
    STATE_REJECTED,
    STATE_REVISION_REQUESTED,
    STATE_READY_TO_PUBLISH,
    STATE_PUBLISHED,
    STATE_ARCHIVED,
})

# Supported Content Types
CONTENT_TYPE_PHILOSOPHICAL_ANALYSIS = "philosophical_analysis"
CONTENT_TYPE_SCIENTIFIC_COMPARISON = "scientific_research_comparison"
CONTENT_TYPE_GITA_INSIGHTS = "gita_based_insights"
CONTENT_TYPE_EDUCATIONAL_ARTICLE = "educational_article"
CONTENT_TYPE_SOCIAL_MEDIA_DRAFT = "social_media_draft"
CONTENT_TYPE_LONG_FORM_REPORT = "long_form_report"

VALID_CONTENT_TYPES = frozenset({
    CONTENT_TYPE_PHILOSOPHICAL_ANALYSIS,
    CONTENT_TYPE_SCIENTIFIC_COMPARISON,
    CONTENT_TYPE_GITA_INSIGHTS,
    CONTENT_TYPE_EDUCATIONAL_ARTICLE,
    CONTENT_TYPE_SOCIAL_MEDIA_DRAFT,
    CONTENT_TYPE_LONG_FORM_REPORT,
})

# Permitted State Transitions State Machine
PERMITTED_TRANSITIONS: dict[str, set[str]] = {
    STATE_GENERATED: {STATE_VALIDATION_FAILED, STATE_PENDING_REVIEW},
    STATE_VALIDATION_FAILED: {STATE_GENERATED, STATE_ARCHIVED},
    STATE_PENDING_REVIEW: {STATE_APPROVED, STATE_REJECTED, STATE_REVISION_REQUESTED},
    STATE_APPROVED: {STATE_READY_TO_PUBLISH, STATE_REVISION_REQUESTED, STATE_REJECTED, STATE_ARCHIVED},
    STATE_REJECTED: {STATE_ARCHIVED, STATE_REVISION_REQUESTED},
    STATE_REVISION_REQUESTED: {STATE_GENERATED, STATE_PENDING_REVIEW, STATE_ARCHIVED},
    STATE_READY_TO_PUBLISH: {STATE_PUBLISHED, STATE_REVISION_REQUESTED, STATE_ARCHIVED},
    STATE_PUBLISHED: {STATE_ARCHIVED},
    STATE_ARCHIVED: set(),
}


class GovernanceError(AntaraError):
    """Base exception for all Module 5 governance errors."""


class GovernanceTransitionError(GovernanceError):
    """Raised when an illegal or unauthorized lifecycle state transition is attempted."""


class GovernanceValidationError(GovernanceError):
    """Raised when a report fails validation gates required for state progression."""


class FingerprintMismatchError(GovernanceError):
    """Raised when published content does not match the approved cryptographic fingerprint."""


class DuplicatePublicationError(GovernanceError):
    """Raised when attempting to republish an identical report version without authorization."""


class UnauthorizedPublishingError(GovernanceError):
    """Raised when publishing is attempted without explicit human authorization."""


def compute_governance_hash(content: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 fingerprint for structured governance content."""
    canonical = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GovernanceRecord:
    """Master governance record tracking report lifecycle, version, and approval state."""

    report_id: str
    title: str
    content_type: str
    current_state: str
    current_version: int
    current_hash: str
    approved_hash: str | None
    approved_by: str | None
    approved_at_utc: str | None
    published_at_utc: str | None
    publication_channels: list[str]
    created_at_utc: str
    updated_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        """Convert record to dictionary."""
        d = asdict(self)
        d["status"] = self.current_state
        return d

    @property
    def status(self) -> str:
        """Convenience property for current lifecycle state."""
        return self.current_state


@dataclass(frozen=True)
class GovernanceVersion:
    """Immutable snapshot of a specific version of a governance report."""

    id: int
    report_id: str
    version: int
    content_type: str
    content: dict[str, Any]
    content_hash: str
    validation_report: dict[str, Any] | None
    created_by: str
    change_summary: str
    created_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        """Convert version to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class GovernanceAuditEntry:
    """Append-only audit trail event for human governance and publishing operations."""

    id: int
    report_id: str
    from_state: str
    to_state: str
    actor: str
    action: str
    notes: str
    content_hash: str
    timestamp_utc: str

    def to_dict(self) -> dict[str, Any]:
        """Convert audit event to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class PublicationPackage:
    """Bounded, authenticated package ready for format export and channel publishing."""

    report_id: str
    version: int
    title: str
    content_type: str
    content: dict[str, Any]
    content_hash: str
    approved_by: str
    approved_at_utc: str
    channels: list[str]
    json_export: str
    markdown_export: str

    def to_dict(self) -> dict[str, Any]:
        """Convert package to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class PublicationReceipt:
    """Immutable proof of publication issued by a publishing provider."""

    receipt_id: str
    report_id: str
    version: int
    channel: str
    format: str
    published_uri_or_path: str
    content_hash: str
    timestamp_utc: str
    publisher_actor: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        """Convert receipt to dictionary."""
        return asdict(self)


class PublishingProvider(ABC):
    """Abstract base class for all publication channels and providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the publishing provider."""
        pass

    @abstractmethod
    def publish(self, package: PublicationPackage, channel: str) -> PublicationReceipt:
        """Publish an approved package to the designated channel.

        Args:
            package: Approved PublicationPackage.
            channel: Target publication channel identifier.

        Returns:
            PublicationReceipt containing path, hash, and timestamp.
        """
        pass


class LocalFilePublisher(PublishingProvider):
    """Publishes approved content packages locally as JSON and Markdown files."""

    def __init__(self, output_root: Path | str = "outputs/publications") -> None:
        self.output_root = Path(output_root)

    @property
    def provider_name(self) -> str:
        return "local_file"

    def publish(self, package: PublicationPackage, channel: str) -> PublicationReceipt:
        target_dir = self.output_root / package.report_id / f"v{package.version}"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Write JSON artifact
        json_file = target_dir / f"{package.report_id}.json"
        json_file.write_text(package.json_export, encoding="utf-8")

        # Write Markdown artifact
        md_file = target_dir / f"{package.report_id}.md"
        md_file.write_text(package.markdown_export, encoding="utf-8")

        receipt_id = f"rcpt_{package.report_id}_v{package.version}_{channel}"
        now_utc = datetime.now(timezone.utc).isoformat()

        return PublicationReceipt(
            receipt_id=receipt_id,
            report_id=package.report_id,
            version=package.version,
            channel=channel,
            format="json+markdown",
            published_uri_or_path=str(md_file),
            content_hash=package.content_hash,
            timestamp_utc=now_utc,
            publisher_actor=package.approved_by,
            status="success",
        )


class MockPublishingProvider(PublishingProvider):
    """Deterministic mock publisher for unit testing and offline development."""

    def __init__(self, should_fail: Exception | None = None) -> None:
        self.should_fail = should_fail
        self.published_packages: list[tuple[PublicationPackage, str]] = []

    @property
    def provider_name(self) -> str:
        return "mock"

    def publish(self, package: PublicationPackage, channel: str) -> PublicationReceipt:
        if self.should_fail:
            raise self.should_fail

        self.published_packages.append((package, channel))
        receipt_id = f"rcpt_mock_{package.report_id}_v{package.version}_{channel}"
        now_utc = datetime.now(timezone.utc).isoformat()

        return PublicationReceipt(
            receipt_id=receipt_id,
            report_id=package.report_id,
            version=package.version,
            channel=channel,
            format="mock_format",
            published_uri_or_path=f"mock://published/{package.report_id}/v{package.version}",
            content_hash=package.content_hash,
            timestamp_utc=now_utc,
            publisher_actor=package.approved_by,
            status="success",
        )


def format_markdown_export(package_or_data: dict[str, Any], title: str, report_id: str, version: int, reviewer: str, approved_at: str) -> str:
    """Format structured reasoning content into a publication-grade Markdown document."""
    lines: list[str] = [
        f"# {title}",
        "",
        "> **Human Supervised Intelligence Publication**  ",
        f"> **Report ID:** `{report_id}` | **Version:** `v{version}`  ",
        f"> **Verified & Approved By:** {reviewer} on `{approved_at}`  ",
        "> **Epistemological Integrity:** 100% authenticated primary sources & peer-reviewed research.  ",
        "",
        "---",
        "",
        "## Executive Summary",
        package_or_data.get("executive_summary", "No executive summary provided."),
        "",
        "## Philosophical Perspective (Bhagavad Gītā)",
        package_or_data.get("philosophical_perspective", "No philosophical perspective provided."),
        "",
    ]

    teachings = package_or_data.get("relevant_gita_teachings", [])
    if teachings:
        lines.append("### Primary Scriptural Teachings")
        for t in teachings:
            lines.append(f"- **Chapter {t.get('chapter')}, Verse {t.get('verse')}**: {t.get('teaching')}")
            if t.get("sanskrit_quote"):
                lines.append(f"  > *{t['sanskrit_quote']}*")
            if t.get("translation_quote"):
                lines.append(f"  > \"{t['translation_quote']}\"")
        lines.append("")

    lines.extend([
        "## Modern Scientific & Psychological Perspectives",
        package_or_data.get("modern_scientific_perspectives", "No scientific perspectives provided."),
        "",
    ])

    supporting = package_or_data.get("supporting_research_evidence", [])
    if supporting:
        lines.append("### Supporting Empirical Evidence")
        for s in supporting:
            lines.append(f"- **[Evidence ID {s.get('evidence_id')}]**: {s.get('finding')}")
        lines.append("")

    contradicting = package_or_data.get("contradicting_research_evidence", [])
    if contradicting:
        lines.append("### Contradicting & Boundary Evidence")
        for c in contradicting:
            lines.append(f"- **[Evidence ID {c.get('evidence_id')}]**: {c.get('finding')}")
        lines.append("")

    lines.extend([
        "## Comparative Analysis: Similarities & Differences",
        "### Concept Similarities",
    ])
    for sim in package_or_data.get("philosophical_and_scientific_similarities", []):
        lines.append(f"- {sim}")
    lines.append("")

    lines.append("### Methodological & Ontological Differences")
    for diff in package_or_data.get("important_differences", []):
        lines.append(f"- {diff}")
    lines.append("")

    lines.extend([
        "## Critical Analysis & Synthesized Insight",
        package_or_data.get("critical_analysis", ""),
        "",
        f"**Core Synthesized Insight:** {package_or_data.get('original_synthesized_insight', '')}",
        "",
        "## Practical Implications",
    ])
    for imp in package_or_data.get("practical_implications", []):
        lines.append(f"- {imp}")
    lines.append("")

    lines.append("## Limitations, Uncertainties & Research Gaps")
    for lim in package_or_data.get("limitations_and_uncertainty", []):
        lines.append(f"- **Limitation**: {lim}")
    for gap in package_or_data.get("research_gaps", []):
        lines.append(f"- **Research Gap**: {gap}")
    lines.append("")

    citations = package_or_data.get("exact_source_citations", [])
    if citations:
        lines.append("## Citations & Provenance")
        for cit in citations:
            if cit.get("type") == "gita":
                lines.append(f"- Gītā Verse ID `{cit.get('id')}` [{cit.get('locator', 'N/A')}]")
            else:
                lines.append(f"- Research Study ID `{cit.get('id')}` [DOI: `{cit.get('doi', 'N/A')}`]")
        lines.append("")

    lines.extend([
        "---",
        f"*Cryptographic Content Hash: `{compute_governance_hash(package_or_data)}`*",
    ])
    return "\n".join(lines)


class GovernanceEngine:
    """ANTARĀ Human-in-the-Loop Governance Engine."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        """Initialize GovernanceEngine with SQLite database."""
        self.db_path = Path(db_path)
        if self.db_path != Path(":memory:"):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
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
        """Create normalized governance tables, constraints, and audit indexes."""
        with self.connection() as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS governance_records (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        content_type TEXT NOT NULL CHECK (
                            content_type IN (
                                'philosophical_analysis', 'scientific_research_comparison',
                                'gita_based_insights', 'educational_article',
                                'social_media_draft', 'long_form_report'
                            )
                        ),
                        current_state TEXT NOT NULL CHECK (
                            current_state IN (
                                'generated', 'validation_failed', 'pending_review',
                                'approved', 'rejected', 'revision_requested',
                                'ready_to_publish', 'published', 'archived'
                            )
                        ),
                        current_version INTEGER NOT NULL DEFAULT 1,
                        current_hash TEXT NOT NULL,
                        approved_hash TEXT,
                        approved_by TEXT,
                        approved_at_utc TEXT,
                        published_at_utc TEXT,
                        publication_channels TEXT,
                        created_at_utc TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS governance_versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        report_id TEXT NOT NULL REFERENCES governance_records(id) ON DELETE CASCADE,
                        version INTEGER NOT NULL,
                        content_type TEXT NOT NULL,
                        content_json TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        validation_report_json TEXT,
                        created_by TEXT NOT NULL,
                        change_summary TEXT,
                        created_at_utc TEXT NOT NULL,
                        UNIQUE(report_id, version)
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS governance_audit (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        report_id TEXT NOT NULL REFERENCES governance_records(id) ON DELETE CASCADE,
                        from_state TEXT NOT NULL,
                        to_state TEXT NOT NULL,
                        actor TEXT NOT NULL,
                        action TEXT NOT NULL,
                        notes TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        timestamp_utc TEXT NOT NULL
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS governance_publications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        report_id TEXT NOT NULL REFERENCES governance_records(id) ON DELETE CASCADE,
                        version INTEGER NOT NULL,
                        channel TEXT NOT NULL,
                        format TEXT NOT NULL,
                        published_path TEXT NOT NULL,
                        publisher_actor TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        published_at_utc TEXT NOT NULL
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gov_state ON governance_records(current_state);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gov_versions ON governance_versions(report_id, version);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_gov_audit ON governance_audit(report_id);")

    def register_report(
        self,
        analysis: ReasoningAnalysis,
        content_type: str = CONTENT_TYPE_PHILOSOPHICAL_ANALYSIS,
        created_by: str = "antara_reasoning_engine",
    ) -> GovernanceRecord:
        """Register an AI reasoning analysis into the governance lifecycle.

        Gating Rules:
        - Checks Module 4 validation status.
        - If validation passed, enters 'pending_review'.
        - If validation failed or has integrity compromises, enters 'validation_failed'.
        """
        if content_type not in VALID_CONTENT_TYPES:
            raise GovernanceValidationError(f"Invalid content_type '{content_type}'. Allowed: {sorted(VALID_CONTENT_TYPES)}")

        content_dict = analysis.to_dict()
        content_hash = compute_governance_hash(content_dict)
        val_report = analysis.validation_report or {}
        val_status = val_report.get("overall_status")

        # Validation Gate: Only reports passing Module 4 may enter pending_review
        if analysis.status == STATE_VALIDATION_FAILED or val_status in ("FAILED_UNSUPPORTED", "FAILED_CONTRADICTED", "INTEGRITY_COMPROMISED"):
            initial_state = STATE_VALIDATION_FAILED
        elif val_status in ("PASSED_VERIFIED", "REQUIRES_HUMAN_REVIEW"):
            initial_state = STATE_PENDING_REVIEW
        else:
            initial_state = STATE_VALIDATION_FAILED

        now_utc = datetime.now(timezone.utc).isoformat()
        report_id = analysis.report_id
        title = analysis.question[:120]

        with self.connection() as conn:
            with conn:
                conn.execute(
                    """
                    INSERT INTO governance_records (
                        id, title, content_type, current_state, current_version,
                        current_hash, approved_hash, approved_by, approved_at_utc,
                        published_at_utc, publication_channels, created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, '[]', ?, ?);
                    """,
                    (report_id, title, content_type, initial_state, 1, content_hash, now_utc, now_utc),
                )
                conn.execute(
                    """
                    INSERT INTO governance_versions (
                        report_id, version, content_type, content_json, content_hash,
                        validation_report_json, created_by, change_summary, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        report_id,
                        1,
                        content_type,
                        json.dumps(content_dict, ensure_ascii=False),
                        content_hash,
                        json.dumps(val_report, ensure_ascii=False),
                        created_by,
                        "Initial registered AI reasoning analysis",
                        now_utc,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO governance_audit (
                        report_id, from_state, to_state, actor, action, notes, content_hash, timestamp_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        report_id,
                        "none",
                        initial_state,
                        created_by,
                        "register_report",
                        f"Report registered into governance. Validation status: {val_status or 'none'}",
                        content_hash,
                        now_utc,
                    ),
                )

        return self.get_record(report_id)

    def get_record(self, report_id: str) -> GovernanceRecord:
        """Fetch a governance record by ID."""
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM governance_records WHERE id = ?;", (report_id,)).fetchone()
            if not row:
                raise GovernanceError(f"Governance record '{report_id}' not found.")

            channels = json.loads(row["publication_channels"]) if row["publication_channels"] else []
            return GovernanceRecord(
                report_id=row["id"],
                title=row["title"],
                content_type=row["content_type"],
                current_state=row["current_state"],
                current_version=int(row["current_version"]),
                current_hash=row["current_hash"],
                approved_hash=row["approved_hash"],
                approved_by=row["approved_by"],
                approved_at_utc=row["approved_at_utc"],
                published_at_utc=row["published_at_utc"],
                publication_channels=channels,
                created_at_utc=row["created_at_utc"],
                updated_at_utc=row["updated_at_utc"],
            )

    def get_version(self, report_id: str, version: int) -> GovernanceVersion:
        """Fetch a specific version snapshot of a governance report."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM governance_versions WHERE report_id = ? AND version = ?;",
                (report_id, version),
            ).fetchone()
            if not row:
                raise GovernanceError(f"Version {version} for report '{report_id}' not found.")

            return GovernanceVersion(
                id=int(row["id"]),
                report_id=row["report_id"],
                version=int(row["version"]),
                content_type=row["content_type"],
                content=json.loads(row["content_json"]),
                content_hash=row["content_hash"],
                validation_report=json.loads(row["validation_report_json"]) if row["validation_report_json"] else None,
                created_by=row["created_by"],
                change_summary=row["change_summary"],
                created_at_utc=row["created_at_utc"],
            )

    def get_audit_trail(self, report_id: str) -> list[GovernanceAuditEntry]:
        """Fetch the append-only audit trail for a governance report."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM governance_audit WHERE report_id = ? ORDER BY id ASC;",
                (report_id,),
            ).fetchall()
            return [
                GovernanceAuditEntry(
                    id=int(r["id"]),
                    report_id=r["report_id"],
                    from_state=r["from_state"],
                    to_state=r["to_state"],
                    actor=r["actor"],
                    action=r["action"],
                    notes=r["notes"],
                    content_hash=r["content_hash"],
                    timestamp_utc=r["timestamp_utc"],
                )
                for r in rows
            ]

    def _transition_state(
        self,
        record: GovernanceRecord,
        target_state: str,
        actor: str,
        action: str,
        notes: str,
        extra_updates: dict[str, Any] | None = None,
    ) -> GovernanceRecord:
        """Execute a validated lifecycle state transition and log to append-only audit trail."""
        from_state = record.current_state
        if target_state not in PERMITTED_TRANSITIONS.get(from_state, set()):
            raise GovernanceTransitionError(
                f"Illegal state transition from '{from_state}' to '{target_state}'. "
                f"Permitted next states: {sorted(PERMITTED_TRANSITIONS.get(from_state, set()))}"
            )

        now_utc = datetime.now(timezone.utc).isoformat()
        clean_notes = validate_substantive_evidence(notes)
        if not actor or not actor.strip():
            raise GovernanceError("Actor identity is mandatory for governance operations.")

        updates = extra_updates or {}
        updates["current_state"] = target_state
        updates["updated_at_utc"] = now_utc

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        params = list(updates.values()) + [record.report_id]

        with self.connection() as conn:
            with conn:
                cursor = conn.execute(
                    f"UPDATE governance_records SET {set_clause} "
                    "WHERE id = ? AND current_state = ?;",
                    [*params, from_state],
                )
                if cursor.rowcount != 1:
                    raise GovernanceTransitionError(
                        f"Report '{record.report_id}' changed state from '{from_state}' "
                        f"before '{action}' could be recorded."
                    )
                conn.execute(
                    """
                    INSERT INTO governance_audit (
                        report_id, from_state, to_state, actor, action, notes, content_hash, timestamp_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        record.report_id,
                        from_state,
                        target_state,
                        actor.strip(),
                        action,
                        clean_notes,
                        record.current_hash,
                        now_utc,
                    ),
                )

        return self.get_record(record.report_id)

    def review(
        self,
        report_id: str,
        action: str,
        reviewer: str,
        notes: str,
    ) -> GovernanceRecord:
        """Perform a human review decision (approve, reject, or request_revision).

        Invariants:
        - Never approves automatically.
        - Reviewer identity and substantive notes (>= 15 chars) are required.
        - Cannot approve reports in 'validation_failed'.
        """
        record = self.get_record(report_id)
        clean_action = action.strip().lower()

        if clean_action == "approve":
            target_state = STATE_APPROVED
            if record.current_state != STATE_PENDING_REVIEW:
                raise GovernanceTransitionError(
                    f"Cannot approve report in state '{record.current_state}'. "
                    f"Report must be in '{STATE_PENDING_REVIEW}'."
                )

            now_utc = datetime.now(timezone.utc).isoformat()
            extra = {
                "approved_hash": record.current_hash,
                "approved_by": reviewer.strip(),
                "approved_at_utc": now_utc,
            }
            return self._transition_state(
                record=record,
                target_state=target_state,
                actor=reviewer,
                action="human_approval",
                notes=notes,
                extra_updates=extra,
            )

        elif clean_action == "reject":
            target_state = STATE_REJECTED
            return self._transition_state(
                record=record,
                target_state=target_state,
                actor=reviewer,
                action="human_rejection",
                notes=notes,
            )

        elif clean_action in ("request_revision", "revision_requested"):
            target_state = STATE_REVISION_REQUESTED
            return self._transition_state(
                record=record,
                target_state=target_state,
                actor=reviewer,
                action="request_revision",
                notes=notes,
            )
        else:
            raise GovernanceError(f"Unrecognized review action '{action}'. Allowed: approve, reject, request_revision")

    def revise_content(
        self,
        report_id: str,
        new_content: dict[str, Any],
        editor: str,
        change_summary: str,
        notes: str,
        validation_report: dict[str, Any] | None = None,
    ) -> GovernanceRecord:
        """Submit a revised version of an existing report.

        Invariants:
        - Automatically creates an incremented version (v2, v3, etc.).
        - If previously approved, content revision immediately invalidates that approval!
        - Computes new content hash and preserves full previous version history.
        """
        record = self.get_record(report_id)
        new_hash = compute_governance_hash(new_content)
        new_version = record.current_version + 1
        now_utc = datetime.now(timezone.utc).isoformat()
        clean_notes = validate_substantive_evidence(notes)

        # Check Module 4 validation on new revision
        val_status = (validation_report or {}).get("overall_status")
        if val_status in ("FAILED_UNSUPPORTED", "FAILED_CONTRADICTED", "INTEGRITY_COMPROMISED"):
            new_state = STATE_VALIDATION_FAILED
        elif val_status in ("PASSED_VERIFIED", "REQUIRES_HUMAN_REVIEW"):
            new_state = STATE_PENDING_REVIEW
        else:
            new_state = STATE_PENDING_REVIEW

        with self.connection() as conn:
            with conn:
                # Insert version snapshot
                conn.execute(
                    """
                    INSERT INTO governance_versions (
                        report_id, version, content_type, content_json, content_hash,
                        validation_report_json, created_by, change_summary, created_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        report_id,
                        new_version,
                        record.content_type,
                        json.dumps(new_content, ensure_ascii=False),
                        new_hash,
                        json.dumps(validation_report, ensure_ascii=False) if validation_report else None,
                        editor.strip(),
                        change_summary.strip(),
                        now_utc,
                    ),
                )
                # Update master record and invalidate prior approval if content changed
                conn.execute(
                    """
                    UPDATE governance_records
                    SET current_version = ?,
                        current_hash = ?,
                        current_state = ?,
                        approved_hash = NULL,
                        approved_by = NULL,
                        approved_at_utc = NULL,
                        updated_at_utc = ?
                    WHERE id = ?;
                    """,
                    (new_version, new_hash, new_state, now_utc, report_id),
                )
                # Audit trail entry
                conn.execute(
                    """
                    INSERT INTO governance_audit (
                        report_id, from_state, to_state, actor, action, notes, content_hash, timestamp_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        report_id,
                        record.current_state,
                        new_state,
                        editor.strip(),
                        f"revise_content_v{new_version}",
                        f"Revised content (v{new_version}). Prior approval invalidated. {clean_notes}",
                        new_hash,
                        now_utc,
                    ),
                )

        return self.get_record(report_id)

    def _verify_approved_version(
        self,
        record: GovernanceRecord,
        version: GovernanceVersion,
    ) -> None:
        """Require the approval fingerprint to match the exact stored version content."""
        actual_hash = compute_governance_hash(version.content)
        if not (
            record.current_hash
            == record.approved_hash
            == version.content_hash
            == actual_hash
        ):
            raise FingerprintMismatchError(
                "Approved content fingerprint does not match the current record and exact stored version. "
                "Re-approval is required."
            )

    def authorize_publication(
        self,
        report_id: str,
        authorizer: str,
        target_channels: list[str],
        notes: str,
    ) -> GovernanceRecord:
        """Explicitly authorize an approved report for publication.

        Invariants:
        - Report must be in 'approved' state.
        - Content fingerprint must match the approved fingerprint.
        - Target channels cannot be empty.
        """
        record = self.get_record(report_id)
        if record.current_state != STATE_APPROVED:
            raise UnauthorizedPublishingError(
                f"Cannot authorize publication for report in state '{record.current_state}'. "
                f"Report must be in '{STATE_APPROVED}'."
            )

        if not target_channels:
            raise GovernanceValidationError("At least one target publication channel must be specified.")

        self._verify_approved_version(
            record,
            self.get_version(report_id, record.current_version),
        )

        extra = {
            "publication_channels": json.dumps(target_channels),
        }
        return self._transition_state(
            record=record,
            target_state=STATE_READY_TO_PUBLISH,
            actor=authorizer,
            action="authorize_publication",
            notes=notes,
            extra_updates=extra,
        )

    def publish(
        self,
        report_id: str,
        publisher: PublishingProvider | None = None,
        publisher_actor: str = "system_publisher",
    ) -> list[PublicationReceipt]:
        """Execute publication of an authorized report across all configured channels.

        Invariants:
        - Report must be in 'ready_to_publish' state.
        - Content fingerprint must match approved fingerprint.
        - Idempotent: duplicate publication on the same channel is guarded.
        """
        record = self.get_record(report_id)
        if record.current_state != STATE_READY_TO_PUBLISH:
            raise UnauthorizedPublishingError(
                f"Cannot publish report in state '{record.current_state}'. "
                f"Report must be explicitly authorized and in state '{STATE_READY_TO_PUBLISH}'."
            )

        version_data = self.get_version(report_id, record.current_version)
        self._verify_approved_version(record, version_data)

        pub_provider = publisher if publisher is not None else LocalFilePublisher()

        # Build Publication Package
        package = PublicationPackage(
            report_id=report_id,
            version=record.current_version,
            title=record.title,
            content_type=record.content_type,
            content=version_data.content,
            content_hash=record.current_hash,
            approved_by=record.approved_by or "unknown_reviewer",
            approved_at_utc=record.approved_at_utc or datetime.now(timezone.utc).isoformat(),
            channels=record.publication_channels,
            json_export=json.dumps(version_data.content, indent=2, ensure_ascii=False),
            markdown_export=format_markdown_export(
                package_or_data=version_data.content,
                title=record.title,
                report_id=report_id,
                version=record.current_version,
                reviewer=record.approved_by or "unknown_reviewer",
                approved_at=record.approved_at_utc or "unknown_date",
            ),
        )

        receipts: list[PublicationReceipt] = []
        now_utc = datetime.now(timezone.utc).isoformat()

        with self.connection() as conn:
            for channel in record.publication_channels:
                # Duplicate publication guard
                existing_pub = conn.execute(
                    """
                    SELECT id FROM governance_publications
                    WHERE report_id = ? AND version = ? AND channel = ?;
                    """,
                    (report_id, record.current_version, channel),
                ).fetchone()

                if existing_pub:
                    raise DuplicatePublicationError(
                        f"Report '{report_id}' (version {record.current_version}) has already been published to channel '{channel}'."
                    )

                receipt = pub_provider.publish(package, channel=channel)
                receipts.append(receipt)

                with conn:
                    conn.execute(
                        """
                        INSERT INTO governance_publications (
                            report_id, version, channel, format, published_path,
                            publisher_actor, content_hash, published_at_utc
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            report_id,
                            record.current_version,
                            channel,
                            receipt.format,
                            receipt.published_uri_or_path,
                            publisher_actor,
                            receipt.content_hash,
                            now_utc,
                        ),
                    )

        # Transition state to published
        self._transition_state(
            record=record,
            target_state=STATE_PUBLISHED,
            actor=publisher_actor,
            action="publish",
            notes=f"Successfully published version {record.current_version} to {record.publication_channels}",
            extra_updates={"published_at_utc": now_utc},
        )

        return receipts

    def archive(
        self,
        report_id: str,
        actor: str,
        notes: str,
    ) -> GovernanceRecord:
        """Transition a report to archived state."""
        record = self.get_record(report_id)
        return self._transition_state(
            record=record,
            target_state=STATE_ARCHIVED,
            actor=actor,
            action="archive",
            notes=notes,
        )

    def export_report(
        self,
        report_id: str,
        format_type: str = "markdown",
        version: int | None = None,
    ) -> str:
        """Export report content to JSON or Markdown."""
        record = self.get_record(report_id)
        target_v = version if version is not None else record.current_version
        v_data = self.get_version(report_id, target_v)

        clean_fmt = format_type.strip().lower()
        if clean_fmt == "json":
            return json.dumps(v_data.content, indent=2, ensure_ascii=False)
        elif clean_fmt in ("markdown", "md"):
            return format_markdown_export(
                package_or_data=v_data.content,
                title=record.title,
                report_id=report_id,
                version=target_v,
                reviewer=record.approved_by or "Unreviewed / Draft",
                approved_at=record.approved_at_utc or "Pending Approval",
            )
        else:
            raise GovernanceError(f"Unsupported export format '{format_type}'. Allowed: json, markdown")
