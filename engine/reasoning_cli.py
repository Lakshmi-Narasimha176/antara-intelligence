"""ANTARĀ Intelligence Engine - AI Reasoning CLI.

Command-line interface to execute philosophical-scientific reasoning syntheses,
inspect 16-dimensional analysis cards, and manage the human review lifecycle.
"""

import argparse
import json
import logging
from pathlib import Path
import sys
from typing import Any

from engine.fact_checker import FactChecker
from engine.knowledge import DEFAULT_DB_PATH
from engine.llm_provider import MockLLMProvider
from engine.openai_provider import OpenAIProvider
from engine.orchestrator import create_brief
from engine.reasoning import ReasoningAnalysis, ReasoningEngine

logger = logging.getLogger("antara.reasoning_cli")


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


def format_reasoning_card(analysis: ReasoningAnalysis) -> str:
    """Format a ReasoningAnalysis into an executive readable terminal card."""
    lines: list[str] = [
        "=" * 72,
        "ANTARĀ AI REASONING & SYNTHESIS REPORT",
        f"Report ID: {analysis.report_id}",
        f"Question:  \"{analysis.question}\"",
        f"Lifecycle Status:      [{analysis.status.upper()}]",
        f"Human Review Required: {analysis.human_review_required}",
        f"Created UTC:           {analysis.created_at_utc}",
        "-" * 72,
        "EXECUTIVE SUMMARY:",
        f"  {analysis.executive_summary}",
        "\nPHILOSOPHICAL PERSPECTIVE (BHAGAVAD GĪTĀ):",
        f"  {analysis.philosophical_perspective}",
    ]

    if analysis.relevant_gita_teachings:
        lines.append("\nRELEVANT GĪTĀ TEACHINGS:")
        for t in analysis.relevant_gita_teachings:
            lines.append(f"  • [Ch {t.get('chapter')}, V {t.get('verse')}] {t.get('teaching')}")
            if t.get("translation_quote"):
                lines.append(f"    Translation: \"{t.get('translation_quote')}\"")

    lines.extend([
        "\nMODERN SCIENTIFIC & PSYCHOLOGICAL PERSPECTIVE:",
        f"  {analysis.modern_scientific_perspectives}",
    ])

    if analysis.supporting_research_evidence:
        lines.append("\nSUPPORTING EMPIRICAL EVIDENCE:")
        for ev in analysis.supporting_research_evidence:
            lines.append(f"  • [Evidence ID {ev.get('evidence_id')}] {ev.get('finding')}")

    if analysis.contradicting_research_evidence:
        lines.append("\nCONTRADICTING / BOUNDARY EVIDENCE:")
        for ev in analysis.contradicting_research_evidence:
            lines.append(f"  • [Evidence ID {ev.get('evidence_id')}] {ev.get('finding')}")

    if analysis.philosophical_and_scientific_similarities:
        lines.append("\nSIMILARITIES & CONCEPTUAL CONVERGENCES:")
        for sim in analysis.philosophical_and_scientific_similarities:
            lines.append(f"  • {sim}")

    if analysis.important_differences:
        lines.append("\nEPISTEMOLOGICAL & ONTOLOGICAL DIFFERENCES:")
        for diff in analysis.important_differences:
            lines.append(f"  • {diff}")

    lines.extend([
        "\nCRITICAL COMPARATIVE ANALYSIS:",
        f"  {analysis.critical_analysis}",
        "\nORIGINAL SYNTHESIZED INSIGHT:",
        f"  {analysis.original_synthesized_insight}",
    ])

    if analysis.practical_implications:
        lines.append("\nPRACTICAL IMPLICATIONS:")
        for imp in analysis.practical_implications:
            lines.append(f"  → {imp}")

    if analysis.limitations_and_uncertainty:
        lines.append("\nLIMITATIONS & UNCERTAINTIES:")
        for lim in analysis.limitations_and_uncertainty:
            lines.append(f"  ⚠ {lim}")

    if analysis.research_gaps:
        lines.append("\nRESEARCH GAPS:")
        for gap in analysis.research_gaps:
            lines.append(f"  ? {gap}")

    val = analysis.validation_report
    if val:
        lines.extend([
            "-" * 72,
            "MODULE 4 FACT-CHECKING AUDIT OUTCOME:",
            f"  Validation Status: {val.get('overall_status')}",
            f"  Total Claims:      {val.get('total_claims')} (Verified: {val.get('verified_claims')}, Unsupported: {val.get('unsupported_claims')}, Contradicted: {val.get('contradicted_claims')})",
        ])

    if analysis.review_audit:
        lines.extend([
            "-" * 72,
            "HUMAN REVIEW AUDIT HISTORY:",
        ])
        for entry in analysis.review_audit:
            lines.append(f"  [{entry.get('reviewed_at_utc')}] {entry.get('previous_status')} -> {entry.get('new_status')} by {entry.get('reviewer')}")
            lines.append(f"    Notes: {entry.get('notes')}")

    lines.append("=" * 72)
    return "\n".join(lines)


def run_synthesize(args: argparse.Namespace) -> None:
    """Execute synthesis pipeline for a question."""
    brief = create_brief(args.question)

    if args.mock:
        provider = MockLLMProvider(model=args.model or "mock-reasoner")
    else:
        try:
            provider = OpenAIProvider(model=args.model)
        except Exception as exc:
            print(f"Warning: OpenAI provider initialization failed ({exc}). Falling back to MockLLMProvider for offline execution.", file=sys.stderr)
            provider = MockLLMProvider()

    engine = ReasoningEngine(db_path=args.db_path, provider=provider)
    analysis = engine.analyze_brief(brief)

    print(format_reasoning_card(analysis))

    out_path = Path(args.out) if args.out else Path("outputs/latest_reasoning_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(analysis.to_json(), encoding="utf-8")
    print(f"\nSaved reasoning synthesis to: {out_path}")


def run_review(args: argparse.Namespace) -> None:
    """Record human approval or rejection on a reasoning report."""
    engine = ReasoningEngine(db_path=args.db_path)
    try:
        updated = engine.review_report(
            report_id=args.report_id,
            decision=args.decision,
            reviewer=args.reviewer,
            notes=args.notes,
        )
        print(f"\nSuccessfully updated report '{updated.report_id}' to [{updated.status.upper()}].")
        print(f"Reviewer: {args.reviewer}")
        print(f"Notes:    {args.notes}\n")
    except Exception as exc:
        print(f"Review Error: {exc}", file=sys.stderr)
        sys.exit(1)


def run_get(args: argparse.Namespace) -> None:
    """Inspect an existing reasoning report by ID."""
    engine = ReasoningEngine(db_path=args.db_path)
    try:
        analysis = engine.get_report(args.report_id)
        print(format_reasoning_card(analysis))
    except Exception as exc:
        print(f"Error fetching report: {exc}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Parse CLI arguments and dispatch commands."""
    configure_utf8_output()

    parser = argparse.ArgumentParser(
        description="ANTARĀ AI Reasoning CLI - Philosophical & Scientific Intelligence Synthesis"
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # synthesize
    p_syn = subparsers.add_parser("synthesize", help="Synthesize philosophical and scientific analysis")
    p_syn.add_argument("question", help="Question to analyze")
    p_syn.add_argument("--mock", action="store_true", help="Force offline MockLLMProvider")
    p_syn.add_argument("--model", help="LLM model identifier")
    p_syn.add_argument("--out", "-o", help="Optional output JSON path")

    # review
    p_rev = subparsers.add_parser("review", help="Record human review decision")
    p_rev.add_argument("--report-id", required=True, help="Report ID to review")
    p_rev.add_argument("--decision", choices=["approved", "rejected"], required=True, help="Review decision")
    p_rev.add_argument("--reviewer", required=True, help="Reviewer name and title")
    p_rev.add_argument("--notes", required=True, help="Substantive review notes (>= 15 characters)")

    # get
    p_get = subparsers.add_parser("get", help="Fetch a reasoning report by ID")
    p_get.add_argument("--report-id", required=True, help="Report ID to inspect")

    args = parser.parse_args()

    if args.command == "synthesize":
        run_synthesize(args)
    elif args.command == "review":
        run_review(args)
    elif args.command == "get":
        run_get(args)


if __name__ == "__main__":
    main()
