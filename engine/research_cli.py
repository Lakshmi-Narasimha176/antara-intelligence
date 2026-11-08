"""ANTARĀ Intelligence Engine - Research Intelligence CLI.

Command-line interface for modern scientific and psychological research retrieval,
evidence classification, human review, and audit trail inspection.
"""

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any

from engine.knowledge import DEFAULT_DB_PATH
from engine.research import (
    EvidenceRecord,
    ResearchManager,
    ResearchSource,
    ResearchSourceDraft,
    SubstantiveReviewError,
)

logger = logging.getLogger("antara.research_cli")


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


def format_source_card(source: ResearchSource, evidence_items: list[EvidenceRecord] | None = None) -> str:
    """Format an academic research source with methodology, sample size, and evidence items."""
    lines: list[str] = [
        "=" * 72,
        f"ANTARĀ RESEARCH SOURCE (ID: {source.id})",
        f"Status: {source.verification_status.upper()} | Fingerprint: {source.content_hash[:16]}...",
        "-" * 72,
        f"Title:   {source.title}",
        f"Authors: {source.authors}",
    ]
    if source.journal:
        lines.append(f"Journal: {source.journal} ({source.year or 'N/A'})")
    if source.doi:
        lines.append(f"DOI:     {source.doi}")
    if source.url:
        lines.append(f"URL:     {source.url}")
    if source.methodology:
        lines.append(f"Method:  {source.methodology}")
    if source.sample_size:
        lines.append(f"Sample:  N = {source.sample_size}")
    if source.study_population:
        lines.append(f"Pop:     {source.study_population}")
    if source.rights_note:
        lines.append(f"Rights:  {source.rights_note}")

    if source.abstract:
        lines.extend(["", "Abstract:", f"  {source.abstract}"])
    if source.limitations:
        lines.extend(["", "Reported Limitations:", f"  {source.limitations}"])

    if evidence_items:
        lines.extend(["", "-" * 72, f"Classified Evidence Findings ({len(evidence_items)}):"])
        for idx, ev in enumerate(evidence_items, start=1):
            lines.append(
                f"\n  [{idx}] Type: {ev.classification.upper()} (Strength: {ev.strength.upper()} | Status: {ev.review_status.upper()})"
            )
            lines.append(f"      Claim:   {ev.claim}")
            lines.append(f"      Finding: {ev.finding}")
            if ev.limitations:
                lines.append(f"      Caveats: {ev.limitations}")

    lines.append("=" * 72)
    return "\n".join(lines)


def format_evidence_card(evidence: EvidenceRecord) -> str:
    """Format an individual evidence record."""
    lines: list[str] = [
        "=" * 72,
        f"ANTARĀ EVIDENCE RECORD (ID: {evidence.id} | Source ID: {evidence.source_id})",
        f"Classification: {evidence.classification.upper()} | Strength: {evidence.strength.upper()}",
        f"Review Status:  {evidence.review_status.upper()}",
        "-" * 72,
        f"Claim:       {evidence.claim}",
        f"Finding:     {evidence.finding}",
    ]
    if evidence.limitations:
        lines.append(f"Limitations: {evidence.limitations}")
    if evidence.source:
        lines.append(f"Source:      {evidence.source.title} ({evidence.source.authors}, {evidence.source.year})")
        if evidence.source.doi:
            lines.append(f"DOI:         {evidence.source.doi}")
    lines.append("=" * 72)
    return "\n".join(lines)


def cmd_init_db(args: argparse.Namespace) -> None:
    """Initialize research schema."""
    mgr = ResearchManager(args.db_path)
    print(f"Initialized ANTARĀ Research schema at: {mgr.db_path}")


def cmd_search_sources(args: argparse.Namespace) -> None:
    """Search research sources."""
    mgr = ResearchManager(args.db_path)
    sources = mgr.search_sources(query=args.query, approved_only=args.approved_only, limit=args.limit)
    print(f"Found {len(sources)} research source(s) (approved_only={args.approved_only}):\n")
    for s in sources:
        print(format_source_card(s))


def cmd_get_source(args: argparse.Namespace) -> None:
    """View full details and classified evidence for a research source."""
    mgr = ResearchManager(args.db_path)
    source = mgr.get_source(args.source_id)
    if not source:
        print(f"Error: Research source ID {args.source_id} not found.", file=sys.stderr)
        sys.exit(1)
    evidence = mgr.search_evidence(limit=100)
    source_evidence = [e for e in evidence if e.source_id == args.source_id]
    print(format_source_card(source, source_evidence))


def cmd_classify(args: argparse.Namespace) -> None:
    """Classify and add an empirical finding linked to a research source."""
    mgr = ResearchManager(args.db_path)
    try:
        ev_id = mgr.add_evidence(
            source_id=args.source_id,
            finding=args.finding,
            claim=args.claim,
            classification=args.classification,
            strength=args.strength,
            limitations=args.limitations,
        )
        print(f"Successfully classified evidence record (ID {ev_id}):")
        ev = mgr.get_evidence(ev_id)
        if ev:
            print(format_evidence_card(ev))
    except Exception as exc:
        print(f"Classification failed: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_search_evidence(args: argparse.Namespace) -> None:
    """Search classified evidence items."""
    mgr = ResearchManager(args.db_path)
    records = mgr.search_evidence(
        query=args.query,
        classification=args.classification,
        approved_only=args.approved_only,
        limit=args.limit,
    )
    print(f"Found {len(records)} evidence record(s):\n")
    for r in records:
        print(format_evidence_card(r))


def cmd_review_source(args: argparse.Namespace) -> None:
    """Record human review decision for a research source."""
    mgr = ResearchManager(args.db_path)
    try:
        audit = mgr.review_source(
            source_id=args.source_id,
            decision=args.decision,
            reviewer=args.reviewer,
            notes=args.notes,
        )
        print("\n--- Research Source Review Recorded ---")
        print(f"Target Source ID: {audit.target_id}")
        print(f"Previous Status:  {audit.previous_status}")
        print(f"New Status:       {audit.new_status.upper()}")
        print(f"Reviewer:         {audit.reviewer}")
        print(f"Notes:            {audit.notes}")
        print(f"Timestamp:        {audit.reviewed_at_utc}")
    except (SubstantiveReviewError, ValueError) as exc:
        print(f"Review Failed: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_review_evidence(args: argparse.Namespace) -> None:
    """Record human review decision for an evidence record."""
    mgr = ResearchManager(args.db_path)
    try:
        audit = mgr.review_evidence(
            evidence_id=args.evidence_id,
            decision=args.decision,
            reviewer=args.reviewer,
            notes=args.notes,
        )
        print("\n--- Research Evidence Review Recorded ---")
        print(f"Target Evidence ID: {audit.target_id}")
        print(f"Previous Status:    {audit.previous_status}")
        print(f"New Status:         {audit.new_status.upper()}")
        print(f"Reviewer:           {audit.reviewer}")
        print(f"Notes:              {audit.notes}")
        print(f"Timestamp:          {audit.reviewed_at_utc}")
    except (SubstantiveReviewError, ValueError) as exc:
        print(f"Review Failed: {exc}", file=sys.stderr)
        sys.exit(1)


def cmd_audit(args: argparse.Namespace) -> None:
    """Display audit trail for a research source or evidence record."""
    mgr = ResearchManager(args.db_path)
    records = mgr.get_audit_history(args.target_type, args.target_id)
    if not records:
        print(f"No audit history found for {args.target_type} ID {args.target_id}")
        return

    print(f"\nAudit Trail for {args.target_type.upper()} ID {args.target_id} ({len(records)} events):")
    print("=" * 72)
    for r in records:
        print(f"[{r.reviewed_at_utc}] Status: {r.previous_status} -> {r.new_status}")
        print(f"  Reviewer: {r.reviewer}")
        print(f"  Notes:    {r.notes}")
        print("-" * 72)


def cmd_import(args: argparse.Namespace) -> None:
    """Import research paper metadata from a UTF-8 JSON file."""
    mgr = ResearchManager(args.db_path)
    path = Path(args.file)
    if not path.is_file():
        print(f"Error: File '{path}' not found.", file=sys.stderr)
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
    data = json.loads(content)
    items: list[dict[str, Any]] = data if isinstance(data, list) else data.get("sources", [])

    print(f"Importing research from '{path}' (dry_run={args.dry_run})...")
    imported = 0
    duplicates = 0
    errors = 0

    for idx, item in enumerate(items, start=1):
        try:
            year_val = item.get("year") or item.get("publication_year")
            if year_val is not None:
                try:
                    year_val = int(year_val)
                except (ValueError, TypeError):
                    year_val = None

            raw_sample = item.get("sample_size")
            sample_size_val = None
            if raw_sample is not None:
                if isinstance(raw_sample, (int, float)):
                    sample_size_val = int(raw_sample)
                elif isinstance(raw_sample, str) and raw_sample.isdigit():
                    sample_size_val = int(raw_sample)

            draft = ResearchSourceDraft(
                title=item["title"],
                authors=item["authors"],
                journal=item.get("journal"),
                year=year_val,
                doi=item.get("doi"),
                url=item.get("url"),
                abstract=item.get("abstract"),
                methodology=item.get("methodology"),
                study_population=item.get("study_population"),
                sample_size=sample_size_val,
                limitations=item.get("limitations"),
                rights_note=item.get("rights_note"),
                provider="json_import",
            )
            if not args.dry_run:
                source_id = mgr.insert_source(draft)
                evidence_claims = item.get("evidence_claims") or item.get("claims") or []
                for claim_item in evidence_claims:
                    mgr.add_evidence(
                        source_id=source_id,
                        finding=claim_item.get("finding") or claim_item.get("claim", ""),
                        claim=claim_item.get("claim") or claim_item.get("finding", ""),
                        classification=claim_item.get("classification", "contextual"),
                        strength=claim_item.get("strength", "moderate"),
                        limitations=claim_item.get("notes") or claim_item.get("limitations"),
                    )
            imported += 1
        except Exception as exc:
            if "already exists" in str(exc).lower():
                duplicates += 1
            else:
                errors += 1
                print(f"  [Row {idx}] Error: {exc}")

    print("\n--- Research Import Summary ---")
    print(f"Dry Run:            {args.dry_run}")
    print(f"Total Processed:    {len(items)}")
    print(f"Successfully Added: {imported}")
    print(f"Duplicates Skipped: {duplicates}")
    print(f"Invalid Rows:       {errors}")


def main() -> None:
    """Parse CLI arguments and dispatch commands."""
    configure_utf8_output()

    parser = argparse.ArgumentParser(
        description="ANTARĀ Research Intelligence CLI - Academic & Scientific Evidence Management"
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init-db
    subparsers.add_parser("init-db", help="Initialize research schema")

    # search-sources
    p_ss = subparsers.add_parser("search-sources", help="Search research sources")
    p_ss.add_argument("--query", "-q", help="Keyword query")
    p_ss.add_argument("--approved-only", action="store_true", help="Filter approved sources only")
    p_ss.add_argument("--limit", type=int, default=20, help="Max results")

    # get-source
    p_gs = subparsers.add_parser("get-source", help="View source details and linked evidence")
    p_gs.add_argument("--source-id", type=int, required=True, help="Research source ID")

    # classify
    p_cl = subparsers.add_parser("classify", help="Classify an empirical finding linked to a source")
    p_cl.add_argument("--source-id", type=int, required=True, help="Research source ID")
    p_cl.add_argument("--finding", required=True, help="Empirical observation/result")
    p_cl.add_argument("--claim", required=True, help="Specific hypothesis or statement tested")
    p_cl.add_argument(
        "--classification",
        choices=["supporting", "contradicting", "contextual", "inconclusive"],
        required=True,
        help="Evidence classification",
    )
    p_cl.add_argument(
        "--strength",
        choices=["high", "moderate", "low", "exploratory"],
        default="moderate",
        help="Evidence strength",
    )
    p_cl.add_argument("--limitations", help="Methodological caveats")

    # search-evidence
    p_se = subparsers.add_parser("search-evidence", help="Search classified evidence")
    p_se.add_argument("--query", "-q", help="Keyword query")
    p_se.add_argument(
        "--classification",
        choices=["supporting", "contradicting", "contextual", "inconclusive"],
        help="Filter by classification",
    )
    p_se.add_argument("--approved-only", action="store_true", help="Filter approved evidence only")
    p_se.add_argument("--limit", type=int, default=20, help="Max results")

    # review-source
    p_rs = subparsers.add_parser("review-source", help="Record human review for a source")
    p_rs.add_argument("--source-id", type=int, required=True, help="Research source ID")
    p_rs.add_argument("--decision", choices=["unreviewed", "approved", "rejected"], required=True)
    p_rs.add_argument("--reviewer", required=True, help="Reviewer identity")
    p_rs.add_argument("--notes", required=True, help="Substantive review notes (>= 15 chars)")

    # review-evidence
    p_re = subparsers.add_parser("review-evidence", help="Record human review for evidence")
    p_re.add_argument("--evidence-id", type=int, required=True, help="Evidence record ID")
    p_re.add_argument("--decision", choices=["unreviewed", "approved", "rejected"], required=True)
    p_re.add_argument("--reviewer", required=True, help="Reviewer identity")
    p_re.add_argument("--notes", required=True, help="Substantive review notes (>= 15 chars)")

    # audit
    p_au = subparsers.add_parser("audit", help="Display audit trail")
    p_au.add_argument("--target-type", choices=["source", "evidence"], required=True)
    p_au.add_argument("--target-id", type=int, required=True)

    # import
    p_im = subparsers.add_parser("import", help="Import research sources from JSON")
    p_im.add_argument("--file", required=True, help="JSON file path")
    p_im.add_argument("--dry-run", action="store_true", help="Validate without committing")

    args = parser.parse_args()

    handlers = {
        "init-db": cmd_init_db,
        "search-sources": cmd_search_sources,
        "get-source": cmd_get_source,
        "classify": cmd_classify,
        "search-evidence": cmd_search_evidence,
        "review-source": cmd_review_source,
        "review-evidence": cmd_review_evidence,
        "audit": cmd_audit,
        "import": cmd_import,
    }

    fn = handlers.get(args.command)
    if fn:
        fn(args)


if __name__ == "__main__":
    main()
