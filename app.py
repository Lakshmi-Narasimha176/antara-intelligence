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
    args = parser.parse_args()

    brief = create_brief(args.question)
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
    print(f"\nSaved brief to: {output_path}")


if __name__ == "__main__":
    main()

