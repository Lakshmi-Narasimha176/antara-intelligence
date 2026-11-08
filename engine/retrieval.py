"""ANTARĀ Intelligence Engine - Knowledge Retrieval Bridge.

Connects Module 1 (Intelligence Orchestrator) with Module 2 (Knowledge Intelligence)
to retrieve verified Bhagavad Gītā knowledge, enforce strict content integrity,
and attach verified primary source evidence to structured research briefs.

Principles:
1. Ground Truth & Provenance: Only cryptographically verified records are retrieved.
2. Tamper Immunity: Unreviewed, rejected, or integrity-invalidated records are strictly excluded.
3. Distinguishability: Primary source text is strictly separated from model interpretations.
4. Robust Fallbacks: Gracefully handles missing databases, non-philosophical queries,
   and zero-result searches without throwing unhandled exceptions.
"""

from dataclasses import asdict, dataclass
import logging
from pathlib import Path
import re
from typing import Any

from engine.knowledge import (
    DEFAULT_DB_PATH,
    KnowledgeBase,
    Verse,
    compute_content_hash,
)
from engine.orchestrator import AntaraError

logger = logging.getLogger(__name__)

# Keywords indicating Bhagavad Gītā or philosophical inquiry
PHILOSOPHICAL_KEYWORDS: tuple[str, ...] = (
    "gita",
    "gītā",
    "bhagavad",
    "bg",
    "krishna",
    "kṛṣṇa",
    "arjuna",
    "dharma",
    "karma",
    "karma-yoga",
    "niṣkāma",
    "yoga",
    "shloka",
    "verse",
    "sanskrit",
    "philosophy",
    "action",
    "fruits",
    "duty",
    "moksha",
    "atman",
    "brahman",
)

# Common words to filter out when extracting search keywords
STOP_WORDS: frozenset[str] = frozenset({
    "what", "why", "how", "when", "where", "who", "which", "does", "do", "did",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "about", "into", "through", "during", "before", "after",
    "above", "below", "between", "under", "again", "further", "then", "once",
    "here", "there", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "can", "will", "just", "should", "now", "tell", "explain", "describe",
    "mean", "meaning", "say", "says", "teach", "teaches",
})


class RetrievalError(AntaraError):
    """Base exception for knowledge retrieval errors."""


@dataclass(frozen=True)
class VerifiedKnowledgeRecord:
    """Immutable representation of a cryptographically verified primary source record.

    Attributes:
        record_id: Database identifier of the verse.
        chapter: Bhagavad Gītā chapter (1-18).
        verse: Verse number (>= 1).
        sanskrit: Authentic Sanskrit Devanagari text.
        transliteration: Romanized transliteration (IAST).
        translation: Translation in target language.
        language: Language code.
        locator: Edition locator (page, section, or folio).
        notes: Contextual scholarly notes.
        content_hash: SHA-256 fingerprint verified against verse content.
        verification_status: Verification state (must be 'verified').
        source: Bibliographic metadata (title, author, translator, edition, year, url, rights).
        evidence_type: Tag distinguishing canonical primary source from AI interpretation.
    """

    record_id: int
    chapter: int
    verse: int
    sanskrit: str
    transliteration: str
    translation: str
    language: str
    locator: str | None
    notes: str | None
    content_hash: str
    verification_status: str
    source: dict[str, Any]
    evidence_type: str = "verified_primary_source"

    def to_dict(self) -> dict[str, Any]:
        """Convert record to JSON-serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class KnowledgeRetrievalResult:
    """Structured result of a knowledge retrieval operation.

    Attributes:
        query: Query or question evaluated.
        retrieval_indicated: Whether the question warranted knowledge retrieval.
        status: Status code ('retrieved_verified', 'no_verified_knowledge_found',
                'retrieval_not_indicated', 'database_unavailable').
        reason: Human-readable explanation of retrieval outcome.
        total_found: Count of verified records retrieved.
        records: List of VerifiedKnowledgeRecord instances.
    """

    query: str
    retrieval_indicated: bool
    status: str
    reason: str
    total_found: int
    records: list[VerifiedKnowledgeRecord]

    def to_dict(self) -> dict[str, Any]:
        """Convert retrieval result to JSON-serializable dictionary."""
        return {
            "query": self.query,
            "retrieval_indicated": self.retrieval_indicated,
            "status": self.status,
            "reason": self.reason,
            "total_found": self.total_found,
            "records": [r.to_dict() for r in self.records],
        }


def should_retrieve_knowledge(question: str, topic: str | None = None) -> bool:
    """Determine whether a research question warrants Bhagavad Gītā knowledge retrieval.

    Args:
        question: User research question.
        topic: Classified topic slug (e.g. 'philosophy', 'human_behavior').

    Returns:
        True if philosophical or Bhagavad Gītā retrieval is indicated, False otherwise.
    """
    if topic == "philosophy":
        return True

    text = question.casefold()

    # Check for explicit verse citations (e.g. 'BG 2.47', 'Chapter 2, Verse 47')
    if extract_verse_references(question):
        return True

    # Word boundary token match for short words like 'bg'
    words = set(re.findall(r"\b\w+\b", text))
    if "bg" in words:
        return True

    # Check substantive philosophical keywords
    return any(keyword in text for keyword in PHILOSOPHICAL_KEYWORDS)


def extract_verse_references(question: str) -> list[tuple[int, int]]:
    """Extract explicit Bhagavad Gītā chapter and verse references from question text.

    Supports formats like:
      - 'Chapter 2, Verse 47'
      - 'Ch 2, v 47'
      - '2.47' or '2:47'
      - 'BG 2.47'

    Args:
        question: Input question text.

    Returns:
        List of valid (chapter, verse) tuples.
    """
    references: list[tuple[int, int]] = []

    # Pattern A: Chapter X, Verse Y (or Ch X, v Y)
    pattern_named = re.compile(
        r"(?:chapter|ch\.?)\s*(\d{1,2})\s*(?:,|\band\b)?\s*(?:verse|v\.?|shloka)?\s*(\d{1,3})",
        re.IGNORECASE,
    )
    for match in pattern_named.finditer(question):
        ch = int(match.group(1))
        v = int(match.group(2))
        if 1 <= ch <= 18 and v >= 1:
            references.append((ch, v))

    # Pattern B: 2.47 or 2:47 with optional BG/Gita prefix
    pattern_numeric = re.compile(
        r"(?:(?:bg|gita|gītā)\s*)?\b(\d{1,2})[:.](\d{1,3})\b",
        re.IGNORECASE,
    )
    for match in pattern_numeric.finditer(question):
        ch = int(match.group(1))
        v = int(match.group(2))
        if 1 <= ch <= 18 and v >= 1:
            ref = (ch, v)
            if ref not in references:
                references.append(ref)

    return references


def extract_search_keywords(question: str) -> list[str]:
    """Extract substantive search keywords from the question, filtering common stop words.

    Args:
        question: Input question text.

    Returns:
        List of candidate search terms.
    """
    cleaned = re.sub(r"[^\w\s-]", " ", question.lower())
    tokens = cleaned.split()
    keywords: list[str] = []
    for token in tokens:
        stripped = token.strip()
        if len(stripped) > 2 and stripped not in STOP_WORDS and not stripped.isdigit():
            if stripped not in keywords:
                keywords.append(stripped)
    return keywords


def _verse_to_verified_record(verse: Verse) -> VerifiedKnowledgeRecord | None:
    """Validate and convert a Verse domain model to a VerifiedKnowledgeRecord.

    Applies strict defense-in-depth cryptographic integrity validation.

    Args:
        verse: Verse instance from KnowledgeBase.

    Returns:
        VerifiedKnowledgeRecord if valid and verified; None if tampered or unverified.
    """
    if verse.verification_status != "verified":
        logger.warning(
            "Rejecting unverified verse %s (status=%s) from verified retrieval.",
            verse.id,
            verse.verification_status,
        )
        return None

    # Cryptographic integrity check: computed SHA-256 must match stored hash
    computed_hash = compute_content_hash(
        chapter=verse.chapter,
        verse=verse.verse,
        sanskrit=verse.sanskrit,
        transliteration=verse.transliteration,
        translation=verse.translation,
        language=verse.language,
    )
    if computed_hash != verse.content_hash:
        logger.error(
            "Integrity check failed for verse %s: computed=%s != stored=%s. Excluding.",
            verse.id,
            computed_hash,
            verse.content_hash,
        )
        return None

    source_dict: dict[str, Any] = {}
    if verse.source:
        source_dict = verse.source.to_dict()
    else:
        source_dict = {"id": verse.source_id, "title": "Unknown Source"}

    return VerifiedKnowledgeRecord(
        record_id=verse.id if verse.id is not None else 0,
        chapter=verse.chapter,
        verse=verse.verse,
        sanskrit=verse.sanskrit,
        transliteration=verse.transliteration,
        translation=verse.translation,
        language=verse.language,
        locator=verse.locator,
        notes=verse.notes,
        content_hash=verse.content_hash,
        verification_status=verse.verification_status,
        source=source_dict,
        evidence_type="verified_primary_source",
    )


def retrieve_knowledge(
    question: str,
    topic: str | None = None,
    kb: KnowledgeBase | None = None,
    db_path: Path | str | None = None,
    limit: int = 5,
) -> KnowledgeRetrievalResult:
    """Retrieve verified Bhagavad Gītā knowledge for an incoming research question.

    Acts as the bridge between Module 1 and Module 2:
    - Decides if retrieval is indicated based on topic and query semantics.
    - Queries KnowledgeBase using verified_only=True.
    - Filters out any unverified, rejected, or modified/tampered records.
    - Returns structured KnowledgeRetrievalResult without inventing facts.

    Args:
        question: User research question.
        topic: Classified topic slug.
        kb: Optional existing KnowledgeBase instance.
        db_path: Optional custom path to SQLite database.
        limit: Maximum records to return.

    Returns:
        Populated KnowledgeRetrievalResult instance.
    """
    # 1. Determine whether knowledge retrieval is indicated
    if not should_retrieve_knowledge(question, topic=topic):
        logger.debug("Knowledge retrieval not indicated for topic '%s'", topic)
        return KnowledgeRetrievalResult(
            query=question,
            retrieval_indicated=False,
            status="retrieval_not_indicated",
            reason="Question topic does not require Bhagavad Gītā primary source retrieval.",
            total_found=0,
            records=[],
        )

    # 2. Acquire knowledge base connection safely
    target_kb = kb
    if target_kb is None:
        target_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        if not target_path.exists() and target_path != Path(":memory:"):
            logger.warning("Knowledge database not found at %s", target_path)
            return KnowledgeRetrievalResult(
                query=question,
                retrieval_indicated=True,
                status="database_unavailable",
                reason=f"Knowledge repository database file not found at: {target_path}",
                total_found=0,
                records=[],
            )
        try:
            target_kb = KnowledgeBase(target_path)
        except Exception as exc:
            logger.error("Failed to initialize KnowledgeBase: %s", exc)
            return KnowledgeRetrievalResult(
                query=question,
                retrieval_indicated=True,
                status="database_unavailable",
                reason=f"Failed to access knowledge repository: {exc}",
                total_found=0,
                records=[],
            )

    # 3. Retrieve verified records
    verified_records: list[VerifiedKnowledgeRecord] = []
    seen_ids: set[int] = set()

    try:
        # Step A: Check for specific chapter/verse mentions
        verse_refs = extract_verse_references(question)
        for ch, v in verse_refs:
            verses = target_kb.search_verses(chapter=ch, verse=v, verified_only=True, limit=limit)
            for verse in verses:
                if verse.id not in seen_ids:
                    record = _verse_to_verified_record(verse)
                    if record:
                        verified_records.append(record)
                        if verse.id is not None:
                            seen_ids.add(verse.id)

        # Step B: Keyword-based semantic search across transliteration, translation, notes
        if len(verified_records) < limit:
            keywords = extract_search_keywords(question)
            for kw in keywords:
                if len(verified_records) >= limit:
                    break
                verses = target_kb.search_verses(query=kw, verified_only=True, limit=limit)
                for verse in verses:
                    if verse.id not in seen_ids:
                        record = _verse_to_verified_record(verse)
                        if record:
                            verified_records.append(record)
                            if verse.id is not None:
                                seen_ids.add(verse.id)
                            if len(verified_records) >= limit:
                                break

        # Step C: Fallback search if question explicitly asks for Gita/philosophy but no keyword matched
        if not verified_records and any(k in question.casefold() for k in ("gita", "gītā", "bhagavad")):
            general_verses = target_kb.search_verses(verified_only=True, limit=limit)
            for verse in general_verses:
                if verse.id not in seen_ids:
                    record = _verse_to_verified_record(verse)
                    if record:
                        verified_records.append(record)
                        if verse.id is not None:
                            seen_ids.add(verse.id)

    except Exception as exc:
        logger.error("Error executing verse search: %s", exc)
        return KnowledgeRetrievalResult(
            query=question,
            retrieval_indicated=True,
            status="error",
            reason=f"Error querying knowledge repository: {exc}",
            total_found=0,
            records=[],
        )

    # 4. Formulate structured response
    if not verified_records:
        return KnowledgeRetrievalResult(
            query=question,
            retrieval_indicated=True,
            status="no_verified_knowledge_found",
            reason="No verified primary source records match the query terms in the knowledge base.",
            total_found=0,
            records=[],
        )

    return KnowledgeRetrievalResult(
        query=question,
        retrieval_indicated=True,
        status="retrieved_verified",
        reason=f"Retrieved {len(verified_records)} cryptographically verified primary source record(s).",
        total_found=len(verified_records),
        records=verified_records,
    )
