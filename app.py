"""ANTARĀ Intelligence Engine - Command-Line Interface.

Entry point for generating human-supervised intelligence briefs and unified Layer 1
intelligence responses from user questions.
Ensures UTF-8 encoding compliance and structured output persistence.
"""

import argparse
import json
import logging
import os
from pathlib import Path
import sys

from engine.orchestrator import create_brief
from engine.search import MockSearchProvider, OpenAIWebSearchProvider, SearchManager
from engine.unified_response import build_unified_response

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

    parser = argparse.ArgumentParser(description="ANTARĀ Intelligence Engine Layer 1")
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
        "--unified",
        action="store_true",
        help="Generate and display comprehensive 12-dimensional Layer 1 Unified Response",
    )
    parser.add_argument(
        "--mock-llm",
        action="store_true",
        help="Force MockLLMProvider for offline deterministic reasoning without network",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Enable live internet search intelligence for current information",
    )
    parser.add_argument(
        "--mock-web",
        action="store_true",
        help="Force MockSearchProvider for offline deterministic web retrieval without network",
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

    # Initialize search manager if web retrieval requested or indicated
    search_provider = None
    if args.mock_web:
        search_provider = MockSearchProvider()
    elif args.web:
        search_provider = OpenAIWebSearchProvider()

    search_mgr = SearchManager(provider=search_provider) if search_provider else None

    brief = create_brief(
        args.question,
        claims=claims_data,
        search_mgr=search_mgr,
        force_web=True if args.web or args.mock_web else None,
    )

    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "latest_brief.json"
    output_path.write_text(json.dumps(brief.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    print("ANTARĀ Intelligence Engine — Layer 1")
    print("=" * 45)
    print(f"Question: {brief.question}")
    print(f"Topic:    {brief.topic}")
    print(f"Status:   {brief.status} (Human Review Required: {brief.human_review_required})")

    # Subsystem Routing Summary
    s_plan = brief.subsystem_plan
    if s_plan:
        print("\nIntelligent Subsystem Routing Plan:")
        print(f"  ├─ Traditional Knowledge (Gītā): {'ENABLED' if s_plan.get('needs_traditional_knowledge') else 'BYPASS'}")
        print(f"  ├─ Scientific Research:         {'ENABLED' if s_plan.get('needs_scientific_research') else 'BYPASS'}")
        print(f"  └─ Real-Time Web Intelligence:  {'ENABLED' if s_plan.get('needs_live_internet') else 'BYPASS'}")

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

    w_ctx = brief.web_context
    if w_ctx and w_ctx.get("total_results", 0) > 0:
        print(f"\nReal-Time Web Intelligence ({w_ctx.get('provider')}):")
        for res in w_ctx.get("results", []):
            pub_date = res.get("published_date") or "Unknown"
            print(f"  - \"{res.get('title')}\"")
            print(f"    URL:       {res.get('url')}")
            print(f"    Domain:    {res.get('source_domain')} [{res.get('credibility_tier')}]")
            print(f"    Published: {pub_date} | Retrieved: {res.get('retrieved_at_utc')}")
            print(f"    Snippet:   {res.get('snippet')}")
        if w_ctx.get("conflicts_detected"):
            print("  [!] DETECTED WEB CONFLICTS / DISAGREEMENTS:")
            for conf in w_ctx["conflicts_detected"]:
                print(f"    * {conf.get('note')}")
    elif w_ctx and w_ctx.get("status") in ("unavailable", "rate_limited", "error"):
        print(f"\nReal-Time Web Intelligence: {w_ctx.get('disclosure_note')}")

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

    # Reasoning and Unified Response
    if args.reason or args.unified:
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

        print("\n" + "=" * 55)
        print("ANTARĀ AI REASONING SYNTHESIS")
        print(f"Report ID: {analysis.report_id}")
        print(f"Status:    [{analysis.status.upper()}] (Human Review Required: {analysis.human_review_required})")
        print(f"\nExecutive Summary:\n  {analysis.executive_summary}")
        print(f"\nSynthesized Insight:\n  {analysis.original_synthesized_insight}")
        print(f"\nSaved reasoning report to: {reason_path}")

        if args.unified:
            unified = build_unified_response(brief, analysis)
            unified_path = output_dir / "latest_unified_response.json"
            unified_path.write_text(unified.to_json(), encoding="utf-8")

            print("\n" + "=" * 55)
            print("LAYER 1 UNIFIED RESPONSE SUMMARY")
            print(f"Direct Answer:           {unified.direct_answer}")
            print(f"Traditional Perspective: {unified.traditional_perspective.get('framework')[:80]}...")
            print(f"Scientific Perspective:  {unified.scientific_perspective.get('framework')[:80]}...")
            print(f"Current Web Sources:     {len(unified.current_developments.get('sources', []))} source(s)")
            print(f"Total Citations:         {len(unified.source_citations)} citation(s) across scripture, research, web")
            print(f"Fact-Check Status:       {unified.fact_checking_results.get('overall_status', 'N/A')}")
            print(f"Governance Status:       [{unified.governance_status.upper()}] (Human Review Required)")
            print(f"\nSaved complete 12-D unified response to: {unified_path}")
        print("=" * 55)

    print(f"\nSaved brief to: {output_path}")


if __name__ == "__main__":
    main()
