"""ANTARĀ Intelligence Engine - Real-Time Search CLI.

Command-line interface for querying web search providers, fetching and sanitizing
web content, inspecting source credibility, and testing robots.txt policies.
"""

import argparse
import json
import logging
import sys

from engine.search import (
    MockSearchProvider,
    OpenAIWebSearchProvider,
    RobotsPolicyChecker,
    SearchManager,
    WebPageFetcher,
)

logger = logging.getLogger("antara.search_cli")


def configure_utf8_output() -> None:
    """Ensure standard output and error streams handle UTF-8 cleanly."""
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


def main() -> None:
    """Entry point for Search CLI."""
    configure_utf8_output()

    parser = argparse.ArgumentParser(description="ANTARĀ Real-Time Search CLI")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Subcommand to execute")

    # Command: search
    search_p = subparsers.add_parser("search", help="Execute live or mock web search")
    search_p.add_argument("query", help="Search query string")
    search_p.add_argument("--max-results", type=int, default=5, help="Maximum results to return")
    search_p.add_argument("--fetch-content", action="store_true", help="Fetch full cleaned page text")
    search_p.add_argument("--mock", action="store_true", help="Use offline MockSearchProvider")
    search_p.add_argument("--json", action="store_true", help="Output full JSON envelope")

    # Command: fetch
    fetch_p = subparsers.add_parser("fetch", help="Safely fetch and sanitize a webpage URL")
    fetch_p.add_argument("url", help="Target URL to fetch")
    fetch_p.add_argument("--max-bytes", type=int, default=50000, help="Maximum bytes to download")

    # Command: check-robots
    robots_p = subparsers.add_parser("check-robots", help="Check robots.txt permissions for URL")
    robots_p.add_argument("url", help="Target URL to inspect")

    args = parser.parse_args()

    if args.command == "search":
        provider = MockSearchProvider() if args.mock else OpenAIWebSearchProvider()
        manager = SearchManager(provider=provider)
        response = manager.search(args.query, max_results=args.max_results, fetch_content=args.fetch_content)

        if args.json:
            print(json.dumps(response.to_dict(), indent=2, ensure_ascii=False))
            return

        print(f"ANTARĀ Web Search: \"{args.query}\"")
        print(f"Provider: {response.provider} | Status: [{response.status.upper()}] | Results: {response.total_results}")
        print(f"Disclosure: {response.disclosure_note}")
        print("-" * 60)

        for i, res in enumerate(response.results, 1):
            print(f"\n[{i}] {res.title}")
            print(f"    URL:         {res.url}")
            print(f"    Domain:      {res.source_domain} ({res.credibility_tier.upper()}, score: {res.credibility_score})")
            print(f"    Published:   {res.published_date or 'N/A'} | Retrieved: {res.retrieved_at_utc}")
            print(f"    Snippet:     {res.snippet}")
            if res.content:
                print(f"    Content Excerpt ({len(res.content)} chars):")
                print(f"      {res.content[:300]}...")

        if response.conflicts_detected:
            print("\n[!] DETECTED CONFLICTS / DISAGREEMENTS:")
            for conf in response.conflicts_detected:
                print(f"  - {conf.get('note')} (Type: {conf.get('type')})")

    elif args.command == "fetch":
        fetcher = WebPageFetcher(max_bytes=args.max_bytes)
        try:
            text = fetcher.fetch_page(args.url)
            print(f"--- Fetched content from {args.url} ({len(text)} characters) ---")
            print(text[:1000] + ("..." if len(text) > 1000 else ""))
        except Exception as exc:
            print(f"Fetch failed: {exc}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "check-robots":
        checker = RobotsPolicyChecker()
        allowed = checker.is_allowed(args.url)
        print(f"Robots.txt check for '{args.url}': {'ALLOWED' if allowed else 'DISALLOWED'}")


if __name__ == "__main__":
    main()
