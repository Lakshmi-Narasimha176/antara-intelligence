"""ANTARĀ Intelligence Engine - Fact-Checking CLI.

Command-line interface for deterministic anti-hallucination validation,
source citation verification, quotation matching, and contradiction detection.
"""

import argparse
import json
import logging
from pathlib import Path
import sys

from engine.fact_checker import (
    Claim,
    FactCheckReport,
    FactChecker,
)
from engine.knowledge import DEFAULT_DB_PATH

logger = logging.getLogger("antara.fact_checker_cli")


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


def format_report_card(report: FactCheckReport) -> str:
    """Format a FactCheckReport into an executive, readable terminal card."""
    lines: list[str] = [
        "=" * 72,
        "ANTARĀ ANTI-HALLUCINATION & FACT-CHECKING REPORT",
        f"Report ID: {report.report_id}",
        f"Brief ID:  {report.brief_id}",
        f"Timestamp: {report.timestamp_utc}",
        "-" * 72,
        f"Overall Outcome:       {report.overall_status}",
        f"Human Review Required: {report.human_review_required}",
        f"Total Claims Assessed: {report.total_claims}",
        f"  ├─ Source Verified:        {report.verified_claims}",
        f"  ├─ Partially Supported:    {report.partially_supported_claims}",
        f"  ├─ Unsupported / Invalid:  {report.unsupported_claims}",
        f"  ├─ Explicit Contradictions:{report.contradicted_claims}",
        f"  ├─ Insufficient Evidence:  {report.insufficient_evidence_claims}",
        f"  └─ Requiring Human Review: {report.requires_human_review_claims}",
        "-" * 72,
    ]

    if report.integrity_failures:
        lines.append("CRITICAL: CRYPTOGRAPHIC INTEGRITY FAILURES DETECTED:")
        for fail in report.integrity_failures:
            lines.append(f"  [!] Claim {fail.get('claim_id')}: Record {fail.get('record_id')} failed hash check!")
        lines.append("-" * 72)

    if report.claims:
        lines.append("CLAIM ASSESSMENT BREAKDOWN:")
        for idx, c in enumerate(report.claims, start=1):
            status_icon = "✓" if c["status"] == "source_verified" else ("✗" if "unsupported" in c["status"] or "contradicted" in c["status"] else "⚠")
            lines.append(f"\n  [{idx}] {status_icon} Claim ID: {c['claim_id']} ({c['status'].upper()})")
            lines.append(f"      Text:   \"{c['claim_text'][:80]}...\"" if len(c['claim_text']) > 80 else f"      Text:   \"{c['claim_text']}\"")
            if c.get("flags"):
                lines.append(f"      Flags:  {', '.join(c['flags'])}")
            for reason in c.get("reasons", []):
                lines.append(f"      Reason: {reason}")

    if report.supporting_sources:
        lines.append("\n" + "-" * 72)
        lines.append("AUTHENTICATED SUPPORTING SOURCES:")
        for src in report.supporting_sources:
            if src.get("type") == "gita":
                lines.append(f"  • [Gita Source {src.get('id')}] {src.get('title')} ({src.get('author')})")
            else:
                lines.append(f"  • [Research Source {src.get('id')}] {src.get('title')} ({src.get('authors')}, {src.get('year')})")

    if report.contradicting_sources:
        lines.append("\n" + "-" * 72)
        lines.append("IDENTIFIED CONTRADICTING SOURCES:")
        for src in report.contradicting_sources:
            lines.append(f"  • [Conflicting Study {src.get('id')}] {src.get('title')} (DOI: {src.get('doi')})")

    if report.unresolved_questions:
        lines.append("\n" + "-" * 72)
        lines.append("UNRESOLVED QUESTIONS & AMBIGUITIES:")
        for q in report.unresolved_questions:
            lines.append(f"  ? {q}")

    lines.append("=" * 72)
    return "\n".join(lines)


def run_validate(args: argparse.Namespace) -> None:
    """Validate a batch of claims from a JSON file."""
    path = Path(args.file)
    if not path.is_file():
        print(f"Error: Claim file '{path}' not found.", file=sys.stderr)
        sys.exit(1)

    content = path.read_text(encoding="utf-8")
    data = json.loads(content)
    raw_claims = data if isinstance(data, list) else data.get("claims", [])

    checker = FactChecker(args.db_path)
    report = checker.validate_claims(raw_claims, brief_id=path.stem)

    print(format_report_card(report))

    out_path = Path(args.out) if args.out else Path("outputs/latest_validation_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report.to_json(), encoding="utf-8")
    print(f"\nSaved validation report to: {out_path}")


def run_check_gita(args: argparse.Namespace) -> None:
    """Quick check for a single Bhagavad Gita reference or quotation."""
    claim = Claim(
        claim_id="cli_gita_1",
        claim_text=args.quote or f"Bhagavad Gita Chapter {args.chapter}, Verse {args.verse}",
        claim_type="gita_quotation" if args.quote else "gita_paraphrase",
        source_type="gita",
        chapter=args.chapter,
        verse=args.verse,
        quoted_text=args.quote,
        quote_field=args.field,
        is_direct_quote=bool(args.quote),
    )
    checker = FactChecker(args.db_path)
    res = checker.validate_claim(claim)

    print("\n--- GĪTĀ CITATION CHECK RESULT ---")
    print(f"Claim ID:       {res.claim_id}")
    print(f"Status:         {res.status.upper()}")
    print(f"Source Exists:  {res.source_exists}")
    print(f"Verified:       {res.source_verified}")
    print(f"Hash Valid:     {res.integrity_valid}")
    if res.quote_matches is not None:
        print(f"Quote Matches:  {res.quote_matches}")
    print(f"Flags:          {', '.join(res.flags) if res.flags else 'none'}")
    for r in res.reasons:
        print(f"Detail:         {r}")
    print("----------------------------------\n")


def main() -> None:
    """Parse CLI arguments and route to appropriate command."""
    configure_utf8_output()

    parser = argparse.ArgumentParser(
        description="ANTARĀ Fact-Checking CLI - Anti-Hallucination & Provenance Verification"
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate
    p_val = subparsers.add_parser("validate", help="Validate a JSON batch of claims")
    p_val.add_argument("--file", "-f", required=True, help="Path to claims JSON file")
    p_val.add_argument("--out", "-o", help="Optional output JSON report path")

    # check-gita
    p_gita = subparsers.add_parser("check-gita", help="Validate a single Gita reference or quotation")
    p_gita.add_argument("--chapter", "-c", type=int, required=True, help="Chapter number (1-18)")
    p_gita.add_argument("--verse", "-v", type=int, required=True, help="Verse number (>= 1)")
    p_gita.add_argument("--quote", "-q", help="Optional quotation text to match")
    p_gita.add_argument(
        "--field",
        choices=["sanskrit", "transliteration", "translation"],
        help="Specific text field to match quotation against",
    )

    args = parser.parse_args()

    if args.command == "validate":
        run_validate(args)
    elif args.command == "check-gita":
        run_check_gita(args)


if __name__ == "__main__":
    main()
