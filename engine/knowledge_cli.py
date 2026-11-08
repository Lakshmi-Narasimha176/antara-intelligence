"""ANTARĀ Intelligence Engine - Knowledge Intelligence CLI.

Command-line interface for Bhagavad Gītā knowledge curation, controlled JSON imports,
tamper detection, and the human verification workflow.
"""

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any

from engine.knowledge import (
    DEFAULT_DB_PATH,
    KnowledgeBase,
    KnowledgeBaseError,
    SubstantiveEvidenceError,
    Verse,
)

logger = logging.getLogger("antara.knowledge_cli")


def configure_utf8_output() -> None:
    """Ensure standard output and error streams handle UTF-8 cleanly on Windows."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


def format_verse_card(verse: Verse) -> str:
    """Format a verse with Sanskrit, transliteration, translation, and source metadata."""
    lines: list[str] = [
        "=" * 72,
        f"ANTARĀ KNOWLEDGE RECORD (Verse ID: {verse.id})",
        f"Status: {verse.verification_status.upper()} | Fingerprint: {verse.content_hash[:16]}...",
        "-" * 72,
        f"Chapter: {verse.chapter}, Verse: {verse.verse} (Language: {verse.language})",
    ]
    if verse.locator:
        lines.append(f"Locator: {verse.locator}")

    lines.extend([
        "",
        "Sanskrit (Devanagari):",
        f"  {verse.sanskrit}",
        "",
        "Transliteration (IAST):",
        f"  {verse.transliteration}",
        "",
        "Translation:",
        f"  {verse.translation}",
        "",
        "Source Provenance:",
    ])

    if verse.source:
        lines.append(f"  Title:       {verse.source.title}")
        lines.append(f"  Author:      {verse.source.author}")
        if verse.source.translator:
            lines.append(f"  Translator:  {verse.source.translator}")
        if verse.source.edition:
            lines.append(f"  Edition:     {verse.source.edition}")
        if verse.source.year:
            lines.append(f"  Year:        {verse.source.year}")
        if verse.source.url:
            lines.append(f"  URL:         {verse.source.url}")
        if verse.source.rights_note:
            lines.append(f"  Rights Note: {verse.source.rights_note}")
    else:
        lines.append(f"  Source ID:   {verse.source_id}")

    if verse.notes:
        lines.extend(["", "Notes:", f"  {verse.notes}"])

    lines.append("=" * 72)
    return "\n".join(lines)


def cmd_init_db(args: argparse.Namespace) -> None:
    """Initialize database schema."""
    kb = KnowledgeBase(args.db_path)
    print(f"Initialized ANTARĀ Knowledge Base schema at: {kb.db_path}")


def cmd_import(args: argparse.Namespace) -> None:
    """Import structured verses from JSON file."""
    kb = KnowledgeBase(args.db_path)
    file_path = Path(args.file)
    if not file_path.is_file():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Importing {file_path} (dry_run={args.dry_run})...")
    summary = kb.import_json(file_path, dry_run=args.dry_run)

    print("\n--- Import Summary ---")
    print(f"Dry Run:            {summary.dry_run}")
    print(f"Total Rows:         {summary.total_rows}")
    print(f"Successfully Added: {summary.imported}")
    print(f"Skipped Duplicates: {summary.skipped_duplicates}")
    print(f"Invalid Rows:       {summary.invalid_rows}")

    if summary.errors:
        print("\nDiagnostics:")
        for err in summary.errors:
            print(f"  [Row {err.get('row')}] {err.get('error')}")


def cmd_get(args: argparse.Namespace) -> None:
    """Retrieve and display a verse record."""
    kb = KnowledgeBase(args.db_path)
    if args.verse_id is not None:
        verse = kb.get_verse(args.verse_id)
        if not verse:
            print(f"No verse found with ID {args.verse_id}", file=sys.stderr)
            sys.exit(1)
        print(format_verse_card(verse))
    elif args.chapter is not None and args.verse is not None:
        verses = kb.get_verses_by_chapter_and_verse(args.chapter, args.verse)
        if not verses:
            print(f"No records found for Chapter {args.chapter}, Verse {args.verse}", file=sys.stderr)
            sys.exit(1)
        for v in verses:
            print(format_verse_card(v))
    else:
        print("Error: Specify either --verse-id or both --chapter and --verse", file=sys.stderr)
        sys.exit(1)


def cmd_search(args: argparse.Namespace) -> None:
    """Search knowledge repository."""
    kb = KnowledgeBase(args.db_path)
    verses = kb.search_verses(
        query=args.query,
        chapter=args.chapter,
        verse=args.verse,
        verified_only=args.verified_only,
        limit=args.limit,
    )
    print(f"Found {len(verses)} matching record(s) (verified_only={args.verified_only}):\n")
    for v in verses:
        print(format_verse_card(v))


def cmd_review(args: argparse.Namespace) -> None:
    """Record human verification decision with required evidence."""
    kb = KnowledgeBase(args.db_path)
    try:
        audit_record = kb.review_verse(
            verse_id=args.verse_id,
            decision=args.decision,
            reviewer=args.reviewer,
            evidence=args.evidence,
            locator=args.locator,
        )
        print("\n--- Human Verification Recorded ---")
        print(f"Verse ID:        {audit_record.verse_id}")
        print(f"Previous Status: {audit_record.previous_status}")
        print(f"New Status:      {audit_record.new_status.upper()}")
        print(f"Reviewer:        {audit_record.reviewer}")
        print(f"Reviewed At:     {audit_record.reviewed_at_utc}")
        print(f"Content Hash:    {audit_record.content_hash}")
        print(f"Evidence Note:   {audit_record.evidence}")
        print("-" * 35)

        # Print updated verse card
        updated = kb.get_verse(args.verse_id)
        if updated:
            print(format_verse_card(updated))
    except (SubstantiveEvidenceError, KnowledgeBaseError, ValueError) as exc:
        print(f"Verification Failed: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_audit(args: argparse.Namespace) -> None:
    """Display append-only audit trail for a verse."""
    kb = KnowledgeBase(args.db_path)
    records = kb.get_audit_history(args.verse_id)
    if not records:
        print(f"No audit history found for verse ID {args.verse_id}")
        return

    print(f"\nAudit Trail for Verse ID {args.verse_id} ({len(records)} events):")
    print("=" * 72)
    for r in records:
        print(f"[{r.reviewed_at_utc}] Status: {r.previous_status} -> {r.new_status}")
        print(f"  Reviewer:     {r.reviewer}")
        print(f"  Content Hash: {r.content_hash}")
        print(f"  Evidence:     {r.evidence}")
        print("-" * 72)


def cmd_verify_integrity(args: argparse.Namespace) -> None:
    """Run cryptographic tamper audit across all database records."""
    kb = KnowledgeBase(args.db_path)
    report = kb.verify_database_integrity()
    print("\n--- Cryptographic Integrity Report ---")
    print(f"Total Records Checked: {report['total_records']}")
    print(f"Valid Records:         {report['valid_records']}")
    print(f"Tampered Records:      {report['tampered_records']}")

    if report["tampered_records"] > 0:
        print("\nWARNING: Discrepancies Detected!")
        for disc in report["discrepancies"]:
            print(f"  [Verse ID {disc['verse_id']}] Ch {disc['chapter']}.{disc['verse']}: {disc['reason']}")
            print(f"    Stored:   {disc['stored_hash']}")
            print(f"    Computed: {disc['computed_hash']}")
    else:
        print("\nAll database records pass cryptographic fingerprint validation.")


def cmd_explain_verification(_args: argparse.Namespace) -> None:
    """Explain the critical distinction between mechanical and human verification."""
    print(
        """
================================================================================
ANTARĀ KNOWLEDGE INTELLIGENCE: MECHANICAL vs. HUMAN VERIFICATION
================================================================================

1. Mechanical Verification (Application Level):
   - Scope: Automated constraints, schema integrity, and cryptographic hashing.
   - Checks:
     * Valid chapter (1-18) and verse numbers.
     * Foreign key relationships to normalized bibliographic sources.
     * Non-null and non-empty textual content.
     * SHA-256 fingerprint verification (detecting bit-rot or unauthorized SQL tampering).
     * Automatic invalidation: resetting 'verified' status to 'unreviewed' if content changes.
   - Limitations:
     * A computer program cannot evaluate if a Sanskrit shloka is authentic.
     * Cannot judge whether an English translation distorts the meaning of 'dharma'.
     * Cannot verify if a stated source volume or manuscript actually exists.

2. Human Verification (Scholarly & Domain Level):
   - Scope: Epistemological, philological, and critical textual authentication.
   - Requirements:
     * Identity of accredited human reviewer.
     * Substantive evidence (comparison against critical editions such as BORI,
       Nirnaya Sagar Press, or Gitapress, along with specific folio/page locators).
     * Analysis of traditional commentaries (e.g. Shankara, Ramanuja, Madhva).
     * Strict Rule: A URL alone or automated search result is NEVER verification.
================================================================================
"""
    )


def main() -> None:
    """Parse command-line arguments and route to appropriate command handler."""
    configure_utf8_output()

    parser = argparse.ArgumentParser(
        description="ANTARĀ Knowledge Intelligence CLI - Source-Traceable Bhagavad Gītā Repository"
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init-db
    subparsers.add_parser("init-db", help="Initialize knowledge base database schema")

    # import
    p_import = subparsers.add_parser("import", help="Import verses from UTF-8 JSON file")
    p_import.add_argument("--file", required=True, help="Path to JSON file to import")
    p_import.add_argument("--dry-run", action="store_true", help="Validate and detect duplicates without committing")

    # get
    p_get = subparsers.add_parser("get", help="Retrieve a verse record")
    p_get.add_argument("--verse-id", type=int, help="Primary key ID of verse")
    p_get.add_argument("--chapter", type=int, help="Chapter number (1-18)")
    p_get.add_argument("--verse", type=int, help="Verse number")

    # search
    p_search = subparsers.add_parser("search", help="Search verses by query or filters")
    p_search.add_argument("--query", "-q", help="Search term across transliteration, translation, or Sanskrit")
    p_search.add_argument("--chapter", "-c", type=int, help="Filter by chapter (1-18)")
    p_search.add_argument("--verse", "-v", type=int, help="Filter by verse number")
    p_search.add_argument("--verified-only", action="store_true", help="Return only cryptographically verified records")
    p_search.add_argument("--limit", type=int, default=50, help="Max records to return (default: 50)")

    # review
    p_review = subparsers.add_parser("review", help="Record human verification decision")
    p_review.add_argument("--verse-id", type=int, required=True, help="Verse ID to review")
    p_review.add_argument(
        "--decision",
        choices=["verified", "rejected", "unreviewed"],
        required=True,
        help="Human review decision",
    )
    p_review.add_argument("--reviewer", required=True, help="Reviewer identity/name")
    p_review.add_argument(
        "--evidence",
        required=True,
        help="Substantive evidence description (URL alone is rejected)",
    )
    p_review.add_argument("--locator", help="Specific reviewed edition locator (e.g., 'p. 119')")

    # audit
    p_audit = subparsers.add_parser("audit", help="Display audit trail for a verse")
    p_audit.add_argument("--verse-id", type=int, required=True, help="Verse ID")

    # verify-integrity
    subparsers.add_parser("verify-integrity", help="Run cryptographic tamper audit on entire database")

    # explain-verification
    subparsers.add_parser("explain-verification", help="Explain mechanical vs. human verification")

    args = parser.parse_args()

    commands = {
        "init-db": cmd_init_db,
        "import": cmd_import,
        "get": cmd_get,
        "search": cmd_search,
        "review": cmd_review,
        "audit": cmd_audit,
        "verify-integrity": cmd_verify_integrity,
        "explain-verification": cmd_explain_verification,
    }

    cmd_fn = commands.get(args.command)
    if cmd_fn:
        cmd_fn(args)


if __name__ == "__main__":
    main()
