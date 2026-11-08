"""ANTARĀ Intelligence Engine - Separately Invoked Live Smoke Tests.

Provides live network and live API smoke tests for:
1. Live internet web search.
2. Live page fetching and robots.txt resolution.
3. Live OpenAI API chat completion and structured reasoning (if OPENAI_API_KEY is configured).

These tests are skipped by default in offline CI / discovery.
To execute live smoke tests in PowerShell:
    $env:ANTARA_ENABLE_LIVE_TESTS = "1"
    python -m unittest tests/test_live_smoke.py -v
"""

import os
import unittest
import urllib.request

from engine.openai_provider import OpenAIProvider
from engine.search import (
    RobotsPolicyChecker,
    WebPageFetcher,
)

RUN_LIVE = os.getenv("ANTARA_ENABLE_LIVE_TESTS") == "1"


class LiveInternetAndAPISmokeTests(unittest.TestCase):
    """Live integration smoke tests requiring real network connectivity."""

    @unittest.skipUnless(RUN_LIVE, "Live smoke tests skipped; set ANTARA_ENABLE_LIVE_TESTS=1 to run.")
    def test_live_network_connectivity(self) -> None:
        """Verify outbound HTTP connectivity to a reliable DNS/HTTP host."""
        try:
            req = urllib.request.Request(
                "https://www.google.com",
                headers={"User-Agent": "ANTARA-SmokeTest/1.0"},
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                self.assertEqual(resp.status, 200)
        except Exception as exc:
            self.skipTest(f"Live network unavailable: {exc}")

    @unittest.skipUnless(RUN_LIVE, "Live smoke tests skipped; set ANTARA_ENABLE_LIVE_TESTS=1 to run.")
    def test_live_robots_txt_and_page_fetch(self) -> None:
        """Verify live robots.txt parsing and sanitized page extraction."""
        checker = RobotsPolicyChecker(timeout=5.0)
        allowed = checker.is_allowed("https://en.wikipedia.org/wiki/Bhagavad_Gita")
        self.assertTrue(allowed)

        fetcher = WebPageFetcher(robots_checker=checker, timeout=8.0, max_bytes=30000)
        try:
            text = fetcher.fetch_page("https://en.wikipedia.org/wiki/Bhagavad_Gita")
            self.assertGreater(len(text), 100)
            self.assertNotIn("<script>", text.lower())
        except Exception as exc:
            self.skipTest(f"Live fetch skipped: {exc}")

    @unittest.skipUnless(RUN_LIVE, "Live smoke tests skipped; set ANTARA_ENABLE_LIVE_TESTS=1 to run.")
    def test_live_openai_api_completion(self) -> None:
        """Verify live OpenAI API structured synthesis if OPENAI_API_KEY is present."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            self.skipTest("OPENAI_API_KEY environment variable not set; skipping live OpenAI call.")

        provider = OpenAIProvider(api_key=api_key, timeout=15.0)
        resp = provider.generate_prompt(
            user_prompt="Return a JSON object with 'status': 'alive' and 'layer': 'Layer 1'.",
            json_mode=True,
        )
        self.assertIsNotNone(resp.raw_json)
        self.assertEqual(resp.raw_json.get("status"), "alive")


if __name__ == "__main__":
    unittest.main()
