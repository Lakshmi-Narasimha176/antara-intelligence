"""ANTARĀ Intelligence Engine - Command-Line Interface.

Entry point for generating human-supervised intelligence briefs from questions.
Ensures UTF-8 encoding compliance and structured output persistence.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from engine.orchestrator import create_brief

logger = logging.getLogger("antara.cli")


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


def configure_logging() -> None:
    """Configure structured logging based on environment variables."""
    log_level = os.getenv("ANTARA_LOG_LEVEL", "WARNING").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.WARNING),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    """Parse CLI arguments, generate brief, and save structured output."""
    configure_utf8_output()
    configure_logging()

    parser = argparse.ArgumentParser(description="ANTARĀ Intelligence Engine v1")
    parser.add_argument("question", help="Question to turn into an intelligence brief")
    parser.add_argument(
        "--claims-file",
        help="Optional path to JSON file containing claims to fact-check against repository",
    )
    parser.add_argument(
        "--reason",
        action="store_true",
        help="Execute AI reasoning synthesis using authenticated primary sources and approved research",
    )
    parser.add_argument(
        "--mock-llm",
        action="store_true",
        help="Force MockLLMProvider for offline deterministic reasoning without network",
    )
    args = parser.parse_args()

    claims_data = None
    if args.claims_file:
        c_path = Path(args.claims_file)
        if c_path.is_file():
            raw_c = json.loads(c_path.read_text(encoding="utf-8"))
            claims_data = raw_c if isinstance(raw_c, list) else raw_c.get("claims", [])
        else:
            print(f"Warning: Claims file '{c_path}' not found.", file=sys.stderr)

    brief = create_brief(args.question, claims=claims_data)
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "latest_brief.json"
    output_path.write_text(json.dumps(brief.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    print("ANTARĀ Intelligence Engine v1")
    print("=" * 34)
    print(f"Question: {brief.question}")
    print(f"Topic: {brief.topic}")
    print(f"Status: {brief.status}")
    print(f"Human review required: {brief.human_review_required}")
    print("\nInitial objectives:")
    for objective in brief.objectives:
        print(f"- {objective}")

    records = brief.knowledge_context.get("records", [])
    if records:
        print("\nVerified Primary Knowledge Sources:")
        for r in records:
            src = r.get("source", {})
            src_str = f"{src.get('title', 'Unknown')} ({src.get('author', 'Unknown')})"
            print(f"- Bhagavad Gītā Ch {r['chapter']}, Verse {r['verse']} [{r.get('locator') or 'N/A'}]")
            print(f"  Source: {src_str}")
            print(f"  Translation: {r['translation']}")
    elif brief.knowledge_context.get("retrieval_indicated"):
        print(f"\nKnowledge Retrieval: {brief.knowledge_context.get('reason')}")

    r_ctx = brief.research_context
    if r_ctx and r_ctx.get("total_evidence", 0) > 0:
        print("\nModern Scientific & Academic Evidence:")
        by_class = r_ctx.get("evidence_by_classification", {})
        for cat in ("supporting", "contradicting", "contextual", "inconclusive"):
            items = by_class.get(cat, [])
            if items:
                print(f"  [{cat.upper()}] ({len(items)} finding(s)):")
                for item in items:
                    print(f"    - Claim: {item['claim']}")
                    print(f"      Finding: {item['finding']}")
                    if item.get("source"):
                        src = item["source"]
                        print(f"      Source: {src.get('title')} ({src.get('authors')}, {src.get('year')})")
        if r_ctx.get("evidence_gaps"):
            print("  [EVIDENCE GAPS & LIMITATIONS]:")
            for gap in r_ctx["evidence_gaps"]:
                print(f"    * {gap}")

    val_ctx = brief.validation_context
    if val_ctx and val_ctx.get("total_claims", 0) > 0:
        print("\nAnti-Hallucination & Fact-Checking Report:")
        print(f"  Overall Outcome:        {val_ctx.get('overall_status')}")
        print(f"  Total Claims Assessed:  {val_ctx.get('total_claims')}")
        print(f"  ├─ Source Verified:         {val_ctx.get('verified_claims')}")
        print(f"  ├─ Partially Supported:     {val_ctx.get('partially_supported_claims')}")
        print(f"  ├─ Unsupported / Invalid:   {val_ctx.get('unsupported_claims')}")
        print(f"  ├─ Explicit Contradictions: {val_ctx.get('contradicted_claims')}")
        print(f"  └─ Requiring Human Review:  {val_ctx.get('requires_human_review_claims')}")
        if val_ctx.get("integrity_failures"):
            print("  [!] CRYPTOGRAPHIC INTEGRITY FAILURES DETECTED!")
        val_path = output_dir / "latest_validation_report.json"
        val_path.write_text(json.dumps(val_ctx, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  Saved validation report to: {val_path}")

    if args.reason:
        from engine.llm_provider import MockLLMProvider
        from engine.openai_provider import OpenAIProvider
        from engine.reasoning import ReasoningEngine

        if args.mock_llm:
            provider = MockLLMProvider()
        else:
            try:
                provider = OpenAIProvider()
            except Exception as exc:
                print(f"\nNotice: OpenAI provider unavailable ({exc}). Using offline MockLLMProvider.")
                provider = MockLLMProvider()

        engine = ReasoningEngine(provider=provider)
        analysis = engine.analyze_brief(brief)
        reason_path = output_dir / "latest_reasoning_report.json"
        reason_path.write_text(analysis.to_json(), encoding="utf-8")

        print("\n" + "=" * 50)
        print("ANTARĀ AI REASONING SYNTHESIS")
        print(f"Report ID: {analysis.report_id}")
        print(f"Status:    [{analysis.status.upper()}] (Human Review Required: {analysis.human_review_required})")
        print(f"\nExecutive Summary:\n  {analysis.executive_summary}")
        print(f"\nSynthesized Insight:\n  {analysis.original_synthesized_insight}")
        print(f"\nSaved reasoning report to: {reason_path}")
        print("=" * 50)

    print(f"\nSaved brief to: {output_path}")


if __name__ == "__main__":
    main()

