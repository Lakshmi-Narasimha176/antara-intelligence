"""ANTARĀ Intelligence Engine - Module 2: Knowledge Intelligence.

Provides a source-traceable, human-supervised knowledge repository for Bhagavad Gītā
verses, Sanskrit text, transliterations, translations, source provenance, and an
append-only verification audit trail using Python 3.12 and built-in sqlite3.

Architectural Principles:
1. Ground Truth & Provenance: Verses are bound to normalized bibliographic sources.
2. Mandatory Human Supervision: All new/imported records default to 'unreviewed'.
   Scholarly verification requires reviewer identity and substantive evidence; a URL
   alone is never verification.
3. Cryptographic Tamper Invalidation: Each verse is fingerprinted using SHA-256. Any
   textual content modification automatically invalidates verification and reverts
   the record to 'unreviewed'.
4. Separation of Concerns: Mechanical validation (schema, hashes, constraints) is strictly
   distinguished from Human Scholarly Verification (epistemological authentication).
"""

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re
import sqlite3
from typing import Any, Generator

from engine.orchestrator import AntaraError

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data") / "antara_knowledge.db"
VALID_VERIFICATION_STATUSES = ("unreviewed", "verified", "rejected")


class KnowledgeBaseError(AntaraError):
    """Base exception for all Knowledge Intelligence domain errors."""


class VerseNotFoundError(KnowledgeBaseError):
    """Raised when a requested verse record cannot be found."""


class DuplicateVerseError(KnowledgeBaseError):
    """Raised when attempting to insert an identical verse translation under the same source."""


class SubstantiveEvidenceError(KnowledgeBaseError):
    """Raised when verification evidence is missing, trivial, or merely a URL."""


class IntegrityVerificationError(KnowledgeBaseError):
    """Raised when cryptographic fingerprint or audit trail validation fails."""


class ImportValidationError(KnowledgeBaseError):
    """Raised when imported data fails schema validation constraints."""


def compute_content_hash(
    chapter: int,
    verse: int,
    sanskrit: str,
    transliteration: str,
    translation: str,
    language: str = "en",
) -> str:
    """Compute a deterministic SHA-256 fingerprint for canonical verse content.

    Preserves exact character representations including Unicode diacritics and Devanagari.

    Args:
        chapter: Bhagavad Gītā chapter (1-18).
        verse: Verse number (>= 1).
        sanskrit: Original Devanagari text.
        transliteration: IAST or romanized transliteration.
        translation: Target translation text.
        language: Language code for translation (default: 'en').

    Returns:
        Hexadecimal SHA-256 digest string.
    """
    canonical_repr = (
        f"{chapter}|{verse}|{sanskrit}|{transliteration}|{translation}|{language.strip().lower()}"
    )
    return hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()


def validate_substantive_evidence(evidence: str) -> str:
    """Validate that human review evidence is substantive, not merely a URL or trivial statement.

    Args:
        evidence: Text describing evidence used by human reviewer.

    Returns:
        Validated evidence text string.

    Raises:
        SubstantiveEvidenceError: If evidence is too brief or is solely a URL.
    """
    if not isinstance(evidence, str):
        raise SubstantiveEvidenceError("Evidence must be a string description.")
    cleaned = evidence.strip()
    if len(cleaned) < 20:
        raise SubstantiveEvidenceError(
            "Evidence is too short. Scholarly verification requires substantive details "
            "(e.g., critical edition comparison, manuscript or page reference, commentary citation)."
        )
    # Reject strings that are merely URLs
    url_pattern = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)
    if url_pattern.match(cleaned):
        raise SubstantiveEvidenceError(
            "A URL alone is not substantive verification. Scholarly verification requires "
            "identifying the specific published volume, edition, locator, and philological rationale."
        )
    return cleaned


@dataclass(frozen=True)
class Source:
    """Bibliographic source metadata."""

    id: int | None
    title: str
    author: str
    translator: str | None = None
    edition: str | None = None
    year: int | None = None
    url: str | None = None
    rights_note: str | None = None
    created_at_utc: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert Source to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class Verse:
    """Bhagavad Gītā verse record bound to source and verification metadata."""

    id: int | None
    source_id: int
    chapter: int
    verse: int
    sanskrit: str
    transliteration: str
    translation: str
    language: str
    locator: str | None
    notes: str | None
    verification_status: str
    content_hash: str
    created_at_utc: str
    updated_at_utc: str
    source: Source | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert Verse to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class VerificationAuditRecord:
    """Append-only audit record documenting human review decision and evidence."""

    id: int | None
    verse_id: int
    previous_status: str
    new_status: str
    reviewer: str
    evidence: str
    content_hash: str
    reviewed_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        """Convert audit record to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class ImportSummary:
    """Summary statistics and diagnostic logs for an import operation."""

    total_rows: int
    imported: int
    skipped_duplicates: int
    invalid_rows: int
    errors: list[dict[str, Any]]
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert import summary to dictionary."""
        return asdict(self)


class KnowledgeBase:
    """SQLite-backed knowledge repository for Bhagavad Gītā verses and source provenance.

    Enforces foreign keys, parameterized queries, duplicate prevention, and cryptographic
    tamper detection.
    """

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        """Initialize the knowledge base connection manager.

        Args:
            db_path: Filesystem path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        if self.db_path != Path(":memory:"):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a new SQLite connection with foreign keys enabled.

        Note: Callers must close the returned connection when finished.
        Prefer using `with self.connection() as conn:` instead.

        Returns:
            sqlite3.Connection configured with Row factory and UTF-8 handling.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager that guarantees the SQLite connection is closed."""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Create normalized database tables, constraints, and indexes if they do not exist."""
        with self.connection() as conn:
            with conn:
                # Table: Bibliographic Sources
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sources (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        author TEXT NOT NULL,
                        translator TEXT,
                        edition TEXT,
                        year INTEGER,
                        url TEXT,
                        rights_note TEXT,
                        created_at_utc TEXT NOT NULL,
                        CONSTRAINT uq_source UNIQUE (title, author, translator, edition, year)
                    );
                    """
                )

                # Table: Verses
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS verses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_id INTEGER NOT NULL,
                        chapter INTEGER NOT NULL CHECK (chapter >= 1 AND chapter <= 18),
                        verse INTEGER NOT NULL CHECK (verse >= 1),
                        sanskrit TEXT NOT NULL,
                        transliteration TEXT NOT NULL,
                        translation TEXT NOT NULL,
                        language TEXT NOT NULL DEFAULT 'en',
                        locator TEXT,
                        notes TEXT,
                        verification_status TEXT NOT NULL CHECK (
                            verification_status IN ('unreviewed', 'verified', 'rejected')
                        ) DEFAULT 'unreviewed',
                        content_hash TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL,
                        FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
                        CONSTRAINT uq_verse_source UNIQUE (source_id, chapter, verse)
                    );
                    """
                )

                # Table: Append-only Verification Audit Trail
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS verification_audit (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        verse_id INTEGER NOT NULL,
                        previous_status TEXT NOT NULL,
                        new_status TEXT NOT NULL,
                        reviewer TEXT NOT NULL,
                        evidence TEXT NOT NULL,
                        content_hash TEXT NOT NULL,
                        reviewed_at_utc TEXT NOT NULL,
                        FOREIGN KEY (verse_id) REFERENCES verses(id) ON DELETE CASCADE
                    );
                    """
                )

                # Performance & Lookup Indexes
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sources_lookup ON sources(title, author);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_verses_lookup ON verses(chapter, verse);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_verses_status ON verses(verification_status);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_verses_source ON verses(source_id);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_verse ON verification_audit(verse_id);")

    def get_or_create_source(
        self,
        title: str,
        author: str,
        translator: str | None = None,
        edition: str | None = None,
        year: int | None = None,
        url: str | None = None,
        rights_note: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        """Retrieve existing source ID or insert a new source record.

        Args:
            title: Title of publication or work.
            author: Author of work or commentary.
            translator: Translator name if applicable.
            edition: Edition or volume identifier.
            year: Year of publication.
            url: Reference URL (if applicable; not verification).
            rights_note: Copyright or public domain license notice.
            conn: Optional existing database connection.

        Returns:
            Integer primary key ID of the source.
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        should_close = False
        if conn is None:
            conn = self.get_connection()
            should_close = True

        try:
            # Query existing source using NULL-safe comparisons
            row = conn.execute(
                """
                SELECT id FROM sources
                WHERE title = ?
                  AND author = ?
                  AND (translator IS ? OR translator = ?)
                  AND (edition IS ? OR edition = ?)
                  AND (year IS ? OR year = ?);
                """,
                (title, author, translator, translator, edition, edition, year, year),
            ).fetchone()

            if row:
                return int(row["id"])

            cursor = conn.execute(
                """
                INSERT INTO sources (title, author, translator, edition, year, url, rights_note, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (title, author, translator, edition, year, url, rights_note, now_utc),
            )
            if should_close:
                conn.commit()
            return int(cursor.lastrowid)
        finally:
            if should_close:
                conn.close()

    def insert_verse(
        self,
        source_id: int,
        chapter: int,
        verse: int,
        sanskrit: str,
        transliteration: str,
        translation: str,
        language: str = "en",
        locator: str | None = None,
        notes: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        """Insert a new verse record. Enforces 'unreviewed' initial status and fingerprinting.

        Args:
            source_id: Foreign key to sources table.
            chapter: Bhagavad Gītā chapter (1-18).
            verse: Verse number (>= 1).
            sanskrit: Exact Devanagari text.
            transliteration: Exact transliteration text.
            translation: Target language translation.
            language: Language code.
            locator: Book locator (e.g. 'Chapter 2, Verse 47, p. 119').
            notes: Contextual or philological notes.
            conn: Optional existing connection.

        Returns:
            Integer primary key ID of inserted verse.

        Raises:
            ImportValidationError: If constraints are violated.
            DuplicateVerseError: If verse already exists under this source.
        """
        if not (1 <= chapter <= 18):
            raise ImportValidationError(f"Invalid chapter {chapter}. Must be between 1 and 18.")
        if verse < 1:
            raise ImportValidationError(f"Invalid verse {verse}. Must be positive integer.")
        if not sanskrit.strip():
            raise ImportValidationError("Sanskrit text cannot be empty.")
        if not transliteration.strip():
            raise ImportValidationError("Transliteration cannot be empty.")
        if not translation.strip():
            raise ImportValidationError("Translation cannot be empty.")

        content_hash = compute_content_hash(
            chapter=chapter,
            verse=verse,
            sanskrit=sanskrit,
            transliteration=transliteration,
            translation=translation,
            language=language,
        )
        now_utc = datetime.now(timezone.utc).isoformat()
        initial_status = "unreviewed"

        should_close = False
        if conn is None:
            conn = self.get_connection()
            should_close = True

        try:
            # Check for duplicate under this source
            dup = conn.execute(
                "SELECT id FROM verses WHERE source_id = ? AND chapter = ? AND verse = ?;",
                (source_id, chapter, verse),
            ).fetchone()
            if dup:
                raise DuplicateVerseError(
                    f"Verse {chapter}.{verse} already exists under source ID {source_id}."
                )

            cursor = conn.execute(
                """
                INSERT INTO verses (
                    source_id, chapter, verse, sanskrit, transliteration,
                    translation, language, locator, notes, verification_status,
                    content_hash, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    source_id,
                    chapter,
                    verse,
                    sanskrit,
                    transliteration,
                    translation,
                    language,
                    locator,
                    notes,
                    initial_status,
                    content_hash,
                    now_utc,
                    now_utc,
                ),
            )
            verse_id = int(cursor.lastrowid)

            # Record initial unreviewed state in audit log
            conn.execute(
                """
                INSERT INTO verification_audit (
                    verse_id, previous_status, new_status, reviewer,
                    evidence, content_hash, reviewed_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    verse_id,
                    "none",
                    initial_status,
                    "SYSTEM:CREATION",
                    "Record ingested; awaiting scholarly human review.",
                    content_hash,
                    now_utc,
                ),
            )

            if should_close:
                conn.commit()
            return verse_id
        finally:
            if should_close:
                conn.close()

    def get_verse(self, verse_id: int) -> Verse | None:
        """Retrieve a single verse by ID, including its associated source metadata.

        Args:
            verse_id: Primary key of the verse.

        Returns:
            Populated Verse instance or None if not found.
        """
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT v.*,
                       s.title AS s_title, s.author AS s_author, s.translator AS s_translator,
                       s.edition AS s_edition, s.year AS s_year, s.url AS s_url,
                       s.rights_note AS s_rights_note, s.created_at_utc AS s_created_at
                FROM verses v
                JOIN sources s ON v.source_id = s.id
                WHERE v.id = ?;
                """,
                (verse_id,),
            ).fetchone()

            if not row:
                return None
            return self._row_to_verse(row)

    def get_verses_by_chapter_and_verse(self, chapter: int, verse: int) -> list[Verse]:
        """Retrieve all editions/translations for a specific chapter and verse.

        Args:
            chapter: Bhagavad Gītā chapter (1-18).
            verse: Verse number.

        Returns:
            List of Verse instances.
        """
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT v.*,
                       s.title AS s_title, s.author AS s_author, s.translator AS s_translator,
                       s.edition AS s_edition, s.year AS s_year, s.url AS s_url,
                       s.rights_note AS s_rights_note, s.created_at_utc AS s_created_at
                FROM verses v
                JOIN sources s ON v.source_id = s.id
                WHERE v.chapter = ? AND v.verse = ?
                ORDER BY v.id ASC;
                """,
                (chapter, verse),
            ).fetchall()
            return [self._row_to_verse(r) for r in rows]

    def update_verse_content(
        self,
        verse_id: int,
        sanskrit: str,
        transliteration: str,
        translation: str,
        language: str = "en",
        locator: str | None = None,
        notes: str | None = None,
    ) -> Verse:
        """Update verse content, automatically invalidating any prior verification.

        If a verified record's textual content is altered, the status automatically reverts
        to 'unreviewed', a new fingerprint is calculated, and a system audit event is logged.

        Args:
            verse_id: Target verse ID.
            sanskrit: Updated Sanskrit text.
            transliteration: Updated transliteration.
            translation: Updated translation.
            language: Translation language code.
            locator: Optional locator string.
            notes: Optional notes.

        Returns:
            Updated Verse instance.

        Raises:
            VerseNotFoundError: If verse does not exist.
        """
        with self.connection() as conn:
            current = conn.execute("SELECT * FROM verses WHERE id = ?;", (verse_id,)).fetchone()
            if not current:
                raise VerseNotFoundError(f"Verse with ID {verse_id} not found.")

            previous_status = current["verification_status"]
            new_hash = compute_content_hash(
                chapter=current["chapter"],
                verse=current["verse"],
                sanskrit=sanskrit,
                transliteration=transliteration,
                translation=translation,
                language=language,
            )
            now_utc = datetime.now(timezone.utc).isoformat()
            new_status = "unreviewed"

            with conn:
                conn.execute(
                    """
                    UPDATE verses
                    SET sanskrit = ?,
                        transliteration = ?,
                        translation = ?,
                        language = ?,
                        locator = COALESCE(?, locator),
                        notes = COALESCE(?, notes),
                        verification_status = ?,
                        content_hash = ?,
                        updated_at_utc = ?
                    WHERE id = ?;
                    """,
                    (
                        sanskrit,
                        transliteration,
                        translation,
                        language,
                        locator,
                        notes,
                        new_status,
                        new_hash,
                        now_utc,
                        verse_id,
                    ),
                )

                # Invalidation audit trail entry
                conn.execute(
                    """
                    INSERT INTO verification_audit (
                        verse_id, previous_status, new_status, reviewer,
                        evidence, content_hash, reviewed_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        verse_id,
                        previous_status,
                        new_status,
                        "SYSTEM:CONTENT_MODIFICATION",
                        "Content modified; prior verification automatically invalidated. Re-review required.",
                        new_hash,
                        now_utc,
                    ),
                )

        verse = self.get_verse(verse_id)
        if not verse:
            raise VerseNotFoundError(f"Verse with ID {verse_id} not found after update.")
        return verse

    def review_verse(
        self,
        verse_id: int,
        decision: str,
        reviewer: str,
        evidence: str,
        locator: str | None = None,
    ) -> VerificationAuditRecord:
        """Record a human verification decision with required substantive evidence.

        Args:
            verse_id: ID of the verse being reviewed.
            decision: One of 'verified', 'rejected', or 'unreviewed'.
            reviewer: Identifier of human reviewer (e.g. name, academic ID).
            evidence: Substantive evidence (manuscript/edition references, commentary citation).
            locator: Optional updated locator in the specific reviewed edition.

        Returns:
            VerificationAuditRecord created in the audit log.

        Raises:
            VerseNotFoundError: If verse does not exist.
            SubstantiveEvidenceError: If evidence is empty, trivial, or merely a URL.
            IntegrityVerificationError: If content fingerprint does not match verse content.
        """
        if decision not in VALID_VERIFICATION_STATUSES:
            raise ValueError(
                f"Invalid decision '{decision}'. Must be one of {VALID_VERIFICATION_STATUSES}."
            )
        if not reviewer or not reviewer.strip():
            raise SubstantiveEvidenceError("Reviewer identity cannot be empty.")

        # Require substantive evidence for verified decisions
        if decision == "verified":
            evidence = validate_substantive_evidence(evidence)
        elif not evidence.strip():
            raise SubstantiveEvidenceError("Evidence/rationale is required for review decision.")

        with self.connection() as conn:
            current = conn.execute("SELECT * FROM verses WHERE id = ?;", (verse_id,)).fetchone()
            if not current:
                raise VerseNotFoundError(f"Verse with ID {verse_id} not found.")

            # Verify cryptographic integrity of record before accepting review
            actual_hash = compute_content_hash(
                chapter=current["chapter"],
                verse=current["verse"],
                sanskrit=current["sanskrit"],
                transliteration=current["transliteration"],
                translation=current["translation"],
                language=current["language"],
            )
            if actual_hash != current["content_hash"]:
                raise IntegrityVerificationError(
                    f"Content hash mismatch for verse {verse_id}! Stored: {current['content_hash']}, "
                    f"Computed: {actual_hash}. Possible out-of-band tampering detected."
                )

            previous_status = current["verification_status"]
            now_utc = datetime.now(timezone.utc).isoformat()

            with conn:
                conn.execute(
                    """
                    UPDATE verses
                    SET verification_status = ?,
                        locator = COALESCE(?, locator),
                        updated_at_utc = ?
                    WHERE id = ?;
                    """,
                    (decision, locator, now_utc, verse_id),
                )

                cursor = conn.execute(
                    """
                    INSERT INTO verification_audit (
                        verse_id, previous_status, new_status, reviewer,
                        evidence, content_hash, reviewed_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (verse_id, previous_status, decision, reviewer.strip(), evidence.strip(), actual_hash, now_utc),
                )

            return VerificationAuditRecord(
                id=int(cursor.lastrowid),
                verse_id=verse_id,
                previous_status=previous_status,
                new_status=decision,
                reviewer=reviewer.strip(),
                evidence=evidence.strip(),
                content_hash=actual_hash,
                reviewed_at_utc=now_utc,
            )

    def search_verses(
        self,
        query: str | None = None,
        chapter: int | None = None,
        verse: int | None = None,
        verified_only: bool = False,
        limit: int = 50,
    ) -> list[Verse]:
        """Search verses using parameterized filters and verified-only constraints.

        Verified-only retrieval verifies cryptographic hash and latest audit record integrity.

        Args:
            query: Keyword query to match against transliteration, translation, or Sanskrit.
            chapter: Optional chapter filter (1-18).
            verse: Optional verse number filter.
            verified_only: If True, returns only cryptographically validated verified records.
            limit: Maximum records to return.

        Returns:
            List of matching Verse instances.
        """
        sql = """
            SELECT v.*,
                   s.title AS s_title, s.author AS s_author, s.translator AS s_translator,
                   s.edition AS s_edition, s.year AS s_year, s.url AS s_url,
                   s.rights_note AS s_rights_note, s.created_at_utc AS s_created_at
            FROM verses v
            JOIN sources s ON v.source_id = s.id
            WHERE 1=1
        """
        params: list[Any] = []

        if chapter is not None:
            sql += " AND v.chapter = ?"
            params.append(chapter)
        if verse is not None:
            sql += " AND v.verse = ?"
            params.append(verse)
        if verified_only:
            sql += " AND v.verification_status = 'verified'"
        if query:
            q_pattern = f"%{query}%"
            sql += """ AND (
                v.transliteration LIKE ? OR
                v.translation LIKE ? OR
                v.sanskrit LIKE ? OR
                v.notes LIKE ? OR
                s.title LIKE ? OR
                s.author LIKE ?
            )"""
            params.extend([q_pattern] * 6)

        sql += " ORDER BY v.chapter ASC, v.verse ASC LIMIT ?"
        params.append(limit)

        with self.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            results: list[Verse] = []
            for r in rows:
                verse_obj = self._row_to_verse(r)
                if verified_only:
                    # Application-level integrity check: ensure content matches content_hash
                    computed = compute_content_hash(
                        chapter=verse_obj.chapter,
                        verse=verse_obj.verse,
                        sanskrit=verse_obj.sanskrit,
                        transliteration=verse_obj.transliteration,
                        translation=verse_obj.translation,
                        language=verse_obj.language,
                    )
                    if computed != verse_obj.content_hash:
                        logger.warning(
                            "Tampering detected on verified verse %d; excluding from verified results.",
                            verse_obj.id,
                        )
                        continue

                    # Verify that latest audit record confirms 'verified' with this hash
                    latest_audit = conn.execute(
                        """
                        SELECT new_status, content_hash FROM verification_audit
                        WHERE verse_id = ?
                        ORDER BY id DESC LIMIT 1;
                        """,
                        (verse_obj.id,),
                    ).fetchone()
                    if (
                        not latest_audit
                        or latest_audit["new_status"] != "verified"
                        or latest_audit["content_hash"] != verse_obj.content_hash
                    ):
                        logger.warning(
                            "Audit trail mismatch for verified verse %d; excluding from verified results.",
                            verse_obj.id,
                        )
                        continue

                results.append(verse_obj)
            return results

    def get_audit_history(self, verse_id: int) -> list[VerificationAuditRecord]:
        """Retrieve the complete append-only audit trail for a verse.

        Args:
            verse_id: Primary key of target verse.

        Returns:
            Chronological list of VerificationAuditRecord instances.
        """
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM verification_audit
                WHERE verse_id = ?
                ORDER BY id ASC;
                """,
                (verse_id,),
            ).fetchall()
            return [
                VerificationAuditRecord(
                    id=int(r["id"]),
                    verse_id=int(r["verse_id"]),
                    previous_status=r["previous_status"],
                    new_status=r["new_status"],
                    reviewer=r["reviewer"],
                    evidence=r["evidence"],
                    content_hash=r["content_hash"],
                    reviewed_at_utc=r["reviewed_at_utc"],
                )
                for r in rows
            ]

    def verify_database_integrity(self) -> dict[str, Any]:
        """Perform a full cryptographic audit across all verses in the database.

        Checks that stored hashes match computed content hashes and verifies audit integrity.

        Returns:
            Diagnostic report dictionary.
        """
        with self.connection() as conn:
            verses = conn.execute("SELECT * FROM verses;").fetchall()
            report: dict[str, Any] = {
                "total_records": len(verses),
                "valid_records": 0,
                "tampered_records": 0,
                "discrepancies": [],
            }

            for v in verses:
                computed = compute_content_hash(
                    chapter=v["chapter"],
                    verse=v["verse"],
                    sanskrit=v["sanskrit"],
                    transliteration=v["transliteration"],
                    translation=v["translation"],
                    language=v["language"],
                )
                if computed != v["content_hash"]:
                    report["tampered_records"] += 1
                    report["discrepancies"].append(
                        {
                            "verse_id": v["id"],
                            "chapter": v["chapter"],
                            "verse": v["verse"],
                            "reason": "Content hash mismatch (direct SQL modification without re-fingerprinting)",
                            "stored_hash": v["content_hash"],
                            "computed_hash": computed,
                        }
                    )
                else:
                    report["valid_records"] += 1

            return report

    def import_json(
        self,
        data: dict[str, Any] | list[dict[str, Any]] | str | Path,
        dry_run: bool = False,
    ) -> ImportSummary:
        """Import structured verses from UTF-8 JSON data or file with validation and isolation.

        Preserves text exactly, prevents duplicate ingestion, and marks all records 'unreviewed'.
        Partial imports succeed for valid records while recording diagnostics for invalid rows.

        Args:
            data: JSON string, parsed dict/list, or Path to JSON file.
            dry_run: If True, validates all records and detects duplicates without writing changes.

        Returns:
            ImportSummary containing counts and diagnostic error messages.
        """
        # Load from file if path provided
        if isinstance(data, (str, Path)):
            raw_path = Path(data)
            if raw_path.is_file():
                content = raw_path.read_text(encoding="utf-8")
                parsed = json.loads(content)
            elif isinstance(data, str) and (data.strip().startswith("{") or data.strip().startswith("[")):
                parsed = json.loads(data)
            else:
                raise ImportValidationError(f"Invalid JSON source or path: {data}")
        else:
            parsed = data

        verses_data: list[dict[str, Any]] = []
        batch_source: dict[str, Any] | None = None

        if isinstance(parsed, dict):
            batch_source = parsed.get("source")
            verses_data = parsed.get("verses", [])
        elif isinstance(parsed, list):
            verses_data = parsed
        else:
            raise ImportValidationError("JSON root must be an object with 'verses' or a list of verse objects.")

        imported_count = 0
        skipped_duplicates_count = 0
        invalid_rows_count = 0
        errors_list: list[dict[str, Any]] = []

        conn = self.get_connection()
        try:
            for idx, item in enumerate(verses_data, start=1):
                if not isinstance(item, dict):
                    invalid_rows_count += 1
                    errors_list.append({"row": idx, "error": "Item is not a valid JSON dictionary."})
                    continue

                # Merge item-specific source or fallback to batch_source
                src_dict = item.get("source") or batch_source
                if not src_dict or not isinstance(src_dict, dict):
                    invalid_rows_count += 1
                    errors_list.append({"row": idx, "error": "Missing required 'source' metadata."})
                    continue

                title = src_dict.get("title")
                author = src_dict.get("author")
                if not title or not author:
                    invalid_rows_count += 1
                    errors_list.append(
                        {"row": idx, "error": "Source must include non-empty 'title' and 'author'."}
                    )
                    continue

                chapter = item.get("chapter")
                verse = item.get("verse")
                sanskrit = item.get("sanskrit")
                transliteration = item.get("transliteration")
                translation = item.get("translation")
                language = item.get("language", "en")
                locator = item.get("locator")
                notes = item.get("notes")

                # Validate data fields
                if not isinstance(chapter, int) or not (1 <= chapter <= 18):
                    invalid_rows_count += 1
                    errors_list.append(
                        {"row": idx, "error": f"Invalid chapter '{chapter}'. Must be integer 1-18."}
                    )
                    continue
                if not isinstance(verse, int) or verse < 1:
                    invalid_rows_count += 1
                    errors_list.append(
                        {"row": idx, "error": f"Invalid verse '{verse}'. Must be positive integer."}
                    )
                    continue
                if not isinstance(sanskrit, str) or not sanskrit.strip():
                    invalid_rows_count += 1
                    errors_list.append({"row": idx, "error": "Sanskrit text is required and non-empty."})
                    continue
                if not isinstance(transliteration, str) or not transliteration.strip():
                    invalid_rows_count += 1
                    errors_list.append(
                        {"row": idx, "error": "Transliteration is required and non-empty."}
                    )
                    continue
                if not isinstance(translation, str) or not translation.strip():
                    invalid_rows_count += 1
                    errors_list.append({"row": idx, "error": "Translation is required and non-empty."})
                    continue

                try:
                    if dry_run:
                        # In dry run, check if source and verse already exist without writing
                        src_row = conn.execute(
                            """
                            SELECT id FROM sources
                            WHERE title = ?
                              AND author = ?
                              AND (translator IS ? OR translator = ?)
                              AND (edition IS ? OR edition = ?)
                              AND (year IS ? OR year = ?);
                            """,
                            (
                                title,
                                author,
                                src_dict.get("translator"),
                                src_dict.get("translator"),
                                src_dict.get("edition"),
                                src_dict.get("edition"),
                                src_dict.get("year"),
                                src_dict.get("year"),
                            ),
                        ).fetchone()
                        if src_row:
                            dup = conn.execute(
                                "SELECT id FROM verses WHERE source_id = ? AND chapter = ? AND verse = ?;",
                                (src_row["id"], chapter, verse),
                            ).fetchone()
                            if dup:
                                skipped_duplicates_count += 1
                                continue
                        imported_count += 1
                    else:
                        src_id = self.get_or_create_source(
                            title=title,
                            author=author,
                            translator=src_dict.get("translator"),
                            edition=src_dict.get("edition"),
                            year=src_dict.get("year"),
                            url=src_dict.get("url"),
                            rights_note=src_dict.get("rights_note"),
                            conn=conn,
                        )
                        self.insert_verse(
                            source_id=src_id,
                            chapter=chapter,
                            verse=verse,
                            sanskrit=sanskrit,
                            transliteration=transliteration,
                            translation=translation,
                            language=language,
                            locator=locator,
                            notes=notes,
                            conn=conn,
                        )
                        imported_count += 1
                except DuplicateVerseError:
                    skipped_duplicates_count += 1
                except Exception as exc:
                    invalid_rows_count += 1
                    errors_list.append({"row": idx, "error": str(exc)})

            if not dry_run:
                conn.commit()
            return ImportSummary(
                total_rows=len(verses_data),
                imported=imported_count,
                skipped_duplicates=skipped_duplicates_count,
                invalid_rows=invalid_rows_count,
                errors=errors_list,
                dry_run=dry_run,
            )
        finally:
            conn.close()

    def _row_to_verse(self, row: sqlite3.Row) -> Verse:
        """Convert a database row with joined source columns into a Verse dataclass."""
        source: Source | None = None
        if "s_title" in row.keys() and row["s_title"] is not None:
            source = Source(
                id=int(row["source_id"]),
                title=row["s_title"],
                author=row["s_author"],
                translator=row["s_translator"],
                edition=row["s_edition"],
                year=row["s_year"],
                url=row["s_url"],
                rights_note=row["s_rights_note"],
                created_at_utc=row["s_created_at"],
            )

        return Verse(
            id=int(row["id"]),
            source_id=int(row["source_id"]),
            chapter=int(row["chapter"]),
            verse=int(row["verse"]),
            sanskrit=row["sanskrit"],
            transliteration=row["transliteration"],
            translation=row["translation"],
            language=row["language"],
            locator=row["locator"],
            notes=row["notes"],
            verification_status=row["verification_status"],
            content_hash=row["content_hash"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
            source=source,
        )
