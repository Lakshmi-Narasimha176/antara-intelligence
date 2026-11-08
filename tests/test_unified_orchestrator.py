"""ANTARĀ Intelligence Engine - Unified Orchestration & Layer 1 Integration Tests.

Verifies the 14 core integration scenarios mandated by Part F:
1. Traditional knowledge-only questions.
2. Live information questions.
3. Scientific research questions.
4. Questions requiring both traditional and modern knowledge.
5. Questions requiring current internet information and stored knowledge.
6. Missing live-search provider handling.
7. Search provider failure resilience.
8. Missing API configuration fallback.
9. Unsupported claims caught and blocked by validation.
10. Invalid citations caught by validation.
11. Contradictory sources identified and surfaced.
12. Human review and approval workflow with substantive notes.
13. Publishing without explicit authorization blocked.
14. Complete end-to-end question processing through publication.
"""

from pathlib import Path
import tempfile
import unittest

from engine.fact_checker import FactChecker
from engine.governance import (
    GovernanceEngine,
    LocalFilePublisher,
    UnauthorizedPublishingError,
)
from engine.knowledge import KnowledgeBase
from engine.llm_provider import MockLLMProvider
from engine.orchestrator import classify_subsystems, create_brief
from engine.reasoning import ReasoningEngine
from engine.research import ResearchManager
from engine.search import (
    MockSearchProvider,
    SearchManager,
    SearchProviderUnavailableError,
    SearchTimeoutError,
)
from engine.unified_engine import UnifiedEngine
from engine.unified_response import UnifiedResponse, build_unified_response


class Layer1UnifiedIntegrationTests(unittest.TestCase):
    """Integration test suite covering all 14 Part F Layer 1 scenarios."""

    def setUp(self) -> None:
        """Create isolated test database and seed authentic test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_antara.db"

        # Initialize knowledge base & seed 1 verified Gita verse
        self.kb = KnowledgeBase(self.db_path)
        self.source_id = self.kb.get_or_create_source(
            title="The Bhagavadgita",
            author="Dr. S. Radhakrishnan",
            translator="Dr. S. Radhakrishnan",
            edition="1993",
            year=1993,
        )
        self.verse_id = self.kb.insert_verse(
            source_id=self.source_id,
            chapter=2,
            verse=47,
            sanskrit="कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।\nमा कर्मफलहेतुर्भूर्मा ते सङ्गोऽस्त्वकर्मणि॥",
            transliteration="karmaṇy evādhikāras te mā phaleṣu kadācana |\nmā karma-phala-hetur bhūr mā te saṅgo 'stv akarmaṇi ||",
            translation="To action alone hast thou a right and never at all to its fruits; let not the fruits of action be thy motive; neither let there be in thee any attachment to inaction.",
            locator="Chapter 2, Verse 47, p. 119",
        )
        self.kb.review_verse(
            verse_id=self.verse_id,
            decision="verified",
            reviewer="Dr. S. Sharma (Sanskrit Philology)",
            evidence="Collated against BORI Critical Edition Vol 7, p. 88.",
        )

        # Initialize research manager & seed approved research source + evidence
        from engine.research import ResearchSourceDraft
        self.research_mgr = ResearchManager(self.db_path)
        draft = ResearchSourceDraft(
            title="The Nature of Procrastination: A Meta-Analytic Review",
            authors="Steel, P.",
            year=2007,
            journal="Psychological Bulletin",
            doi="10.1037/0033-2909.133.1.65",
            methodology="Meta-analysis",
            sample_size=212,
        )
        self.res_src_id = self.research_mgr.insert_source(draft)
        self.research_mgr.review_source(
            source_id=self.res_src_id,
            decision="approved",
            reviewer="Dr. E. Vance, Cognitive Psychology",
            notes="Methodology verified against PRISMA standards.",
        )
        self.evidence_id_1 = self.research_mgr.add_evidence(
            source_id=self.res_src_id,
            claim="Procrastination correlates strongly with task delay discounting.",
            finding="Meta-analysis showed strong correlation with delay discounting (r = 0.41).",
            classification="supporting",
            strength="high",
        )
        self.research_mgr.review_evidence(
            evidence_id=self.evidence_id_1,
            decision="approved",
            reviewer="Dr. E. Vance, Cognitive Psychology",
            notes="Statistical effect size corroborated from Table 3 in Psychological Bulletin paper.",
        )

        # Seed contradicting evidence record
        self.evidence_id_2 = self.research_mgr.add_evidence(
            source_id=self.res_src_id,
            claim="Perfectionism is a primary causal driver of task avoidance.",
            finding="Observed near-zero correlation between clinical perfectionism and delay (r = -0.03).",
            classification="contradicting",
            strength="moderate",
        )
        self.research_mgr.review_evidence(
            evidence_id=self.evidence_id_2,
            decision="approved",
            reviewer="Dr. E. Vance, Cognitive Psychology",
            notes="Contradicting finding corroborated from Section 4.2 of published study.",
        )

        # Initialize search provider and manager
        self.search_provider = MockSearchProvider()
        self.search_mgr = SearchManager(provider=self.search_provider)

        # Initialize fact-checker, governance, and unified engine
        self.fact_checker = FactChecker(self.db_path)
        self.governance = GovernanceEngine(self.db_path)
        self.llm_provider = MockLLMProvider()
        self.unified_engine = UnifiedEngine(
            db_path=self.db_path,
            llm_provider=self.llm_provider,
            search_provider=self.search_provider,
            fact_checker=self.fact_checker,
            governance_engine=self.governance,
        )

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    # 1. Traditional knowledge-only question
    def test_01_traditional_knowledge_only_question(self) -> None:
        """Requirement 1: Traditional-only question retrieves Gita verses and bypasses web search."""
        q = "What does the Bhagavad Gita teach in Chapter 2, Verse 47 regarding action?"
        plan = classify_subsystems(q)
        self.assertTrue(plan.needs_traditional_knowledge)
        self.assertFalse(plan.needs_live_internet)

        brief = create_brief(q, kb=self.kb, search_mgr=self.search_mgr)
        self.assertGreaterEqual(len(brief.knowledge_context.get("records", [])), 1)
        self.assertEqual(brief.web_context.get("status"), "bypassed")
        self.assertEqual(brief.web_context.get("total_results"), 0)

    # 2. Live information question
    def test_02_live_information_question(self) -> None:
        """Requirement 2: Live information question retrieves web data and bypasses Gita."""
        q = "What are the latest 2026 technological trends in quantum computing?"
        plan = classify_subsystems(q)
        self.assertTrue(plan.needs_live_internet)
        self.assertFalse(plan.needs_traditional_knowledge)

        brief = create_brief(q, kb=self.kb, search_mgr=self.search_mgr)
        self.assertGreaterEqual(brief.web_context.get("total_results", 0), 1)
        self.assertFalse(brief.knowledge_context.get("retrieval_indicated", True))
        self.assertEqual(len(brief.knowledge_context.get("records", [])), 0)

    # 3. Scientific research question
    def test_03_scientific_research_question(self) -> None:
        """Requirement 3: Scientific research question retrieves empirical evidence."""
        q = "Why do people procrastinate according to empirical psychological studies?"
        plan = classify_subsystems(q)
        self.assertTrue(plan.needs_scientific_research)
        self.assertFalse(plan.needs_traditional_knowledge)

        brief = create_brief(q, kb=self.kb, research_mgr=self.research_mgr, search_mgr=self.search_mgr)
        self.assertGreaterEqual(brief.research_context.get("total_evidence", 0), 1)
        self.assertEqual(len(brief.knowledge_context.get("records", [])), 0)

    # 4. Questions requiring both traditional and modern knowledge
    def test_04_hybrid_traditional_and_modern_knowledge(self) -> None:
        """Requirement 4: Hybrid philosophy and science inquiry invokes both repositories."""
        q = "How does the Bhagavad Gita's concept of Nishkama Karma compare with empirical research on procrastination?"
        plan = classify_subsystems(q)
        self.assertTrue(plan.needs_traditional_knowledge)
        self.assertTrue(plan.needs_scientific_research)
        self.assertFalse(plan.needs_live_internet)

        brief = create_brief(q, kb=self.kb, research_mgr=self.research_mgr, search_mgr=self.search_mgr)
        self.assertGreaterEqual(len(brief.knowledge_context.get("records", [])), 1)
        self.assertGreaterEqual(brief.research_context.get("total_evidence", 0), 1)
        self.assertEqual(brief.web_context.get("status"), "bypassed")

    # 5. Questions requiring current internet information and stored knowledge
    def test_05_hybrid_stored_knowledge_and_current_internet(self) -> None:
        """Requirement 5: Multi-domain inquiry invokes traditional, empirical, and web subsystems."""
        q = "How does Gita Chapter 2, Verse 47 and empirical psychology research on procrastination apply to recent 2026 workplace trends?"
        plan = classify_subsystems(q)
        self.assertTrue(plan.needs_traditional_knowledge)
        self.assertTrue(plan.needs_scientific_research)
        self.assertTrue(plan.needs_live_internet)

        brief = create_brief(q, kb=self.kb, research_mgr=self.research_mgr, search_mgr=self.search_mgr)
        self.assertGreaterEqual(len(brief.knowledge_context.get("records", [])), 1)
        self.assertGreaterEqual(brief.research_context.get("total_evidence", 0), 1)
        self.assertGreaterEqual(brief.web_context.get("total_results", 0), 1)

    # 6. Missing live-search provider
    def test_06_missing_live_search_provider_handling(self) -> None:
        """Requirement 6: Orchestrator handles missing search manager gracefully."""
        q = "What are the latest 2026 quantum computing updates?"
        brief = create_brief(q, kb=self.kb, search_mgr=None)
        # Should not crash; defaults to search manager or handles safely
        self.assertIsNotNone(brief.web_context)

    # 7. Search provider failures
    def test_07_search_provider_failure_resilience(self) -> None:
        """Requirement 7: Search provider timeout/failure results in clean status disclosure."""
        failing_search = MockSearchProvider(force_timeout=True)
        mgr = SearchManager(provider=failing_search)

        q = "What are the latest 2026 updates?"
        brief = create_brief(q, kb=self.kb, search_mgr=mgr, force_web=True)
        self.assertEqual(brief.web_context.get("status"), "unavailable")
        self.assertIn("timed out", brief.web_context.get("disclosure_note", ""))

    # 8. Missing API configuration
    def test_08_missing_api_configuration_fallback(self) -> None:
        """Requirement 8: Missing OpenAI credentials fall back to MockLLMProvider without crashing."""
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            engine = UnifiedEngine(
                db_path=self.db_path,
                llm_provider=None,  # triggers fallback
                search_provider=self.search_provider,
                fact_checker=self.fact_checker,
                governance_engine=self.governance,
            )
            self.assertIsInstance(engine.llm_provider, MockLLMProvider)
            brief, analysis, unified = engine.process("What does Gita 2.47 teach?")
            self.assertIsNotNone(unified.direct_answer)

    # 9. Unsupported claims caught by validation
    def test_09_unsupported_claims_caught_by_validation(self) -> None:
        """Requirement 9: Output with unsupported claims transitions to validation_failed."""
        # Provider returns output referencing non-existent verse 999
        unsupported_payload = {
            "executive_summary": "Summary with non-existent verse.",
            "philosophical_perspective": "Philosophy.",
            "relevant_gita_teachings": [],
            "modern_scientific_perspectives": "Science.",
            "supporting_research_evidence": [],
            "contradicting_research_evidence": [],
            "philosophical_and_scientific_similarities": [],
            "important_differences": [],
            "critical_analysis": "Analysis.",
            "original_synthesized_insight": "Insight.",
            "practical_implications": [],
            "limitations_and_uncertainty": [],
            "research_gaps": [],
            "exact_source_citations": [],
            "claims_requiring_human_review": [
                {
                    "claim_id": "c_fake",
                    "claim_text": "Non-existent scripture teaching",
                    "source_type": "gita",
                    "record_id": 9999,  # does not exist
                    "chapter": 18,
                    "verse": 99,
                }
            ],
        }
        bad_provider = MockLLMProvider(mock_response=unsupported_payload)
        reasoner = ReasoningEngine(db_path=self.db_path, provider=bad_provider, fact_checker=self.fact_checker)
        brief = create_brief("What does Gita teach?", kb=self.kb)
        analysis = reasoner.analyze_brief(brief)

        self.assertEqual(analysis.status, "validation_failed")

    # 10. Invalid citations
    def test_10_invalid_citations_caught_by_validation(self) -> None:
        """Requirement 10: Mismatched quotation text fails verification."""
        mismatched_payload = {
            "executive_summary": "Summary.",
            "philosophical_perspective": "Perspective.",
            "relevant_gita_teachings": [],
            "modern_scientific_perspectives": "Science.",
            "supporting_research_evidence": [],
            "contradicting_research_evidence": [],
            "philosophical_and_scientific_similarities": [],
            "important_differences": [],
            "critical_analysis": "Critical.",
            "original_synthesized_insight": "Original.",
            "practical_implications": [],
            "limitations_and_uncertainty": [],
            "research_gaps": [],
            "exact_source_citations": [],
            "claims_requiring_human_review": [
                {
                    "claim_id": "c_mismatch",
                    "claim_text": "This quote is completely fabricated and does not match the verse text at all.",
                    "source_type": "gita",
                    "record_id": self.verse_id,
                    "chapter": 2,
                    "verse": 47,
                    "is_direct_quote": True,
                    "quoted_text": "Fabricated text not matching translation.",
                    "quote_field": "translation",
                }
            ],
        }
        bad_provider = MockLLMProvider(mock_response=mismatched_payload)
        reasoner = ReasoningEngine(db_path=self.db_path, provider=bad_provider, fact_checker=self.fact_checker)
        brief = create_brief("What does Gita teach?", kb=self.kb)
        analysis = reasoner.analyze_brief(brief)

        self.assertEqual(analysis.status, "validation_failed")

    # 11. Contradictory sources
    def test_11_contradictory_sources_detected(self) -> None:
        """Requirement 11: Contradicting research findings are captured in response."""
        brief, analysis, unified = self.unified_engine.process(
            "Why do people procrastinate according to empirical research?"
        )
        # Verify contradicting evidence is present
        self.assertGreaterEqual(len(unified.contradicting_evidence), 1)
        first_contra = unified.contradicting_evidence[0]
        self.assertIn("contradict", str(first_contra).lower())

    # 12. Human review and approval workflow
    def test_12_human_review_and_approval_workflow(self) -> None:
        """Requirement 12: Substantive human review transitions report to approved."""
        brief, analysis, unified = self.unified_engine.process(
            "What does Gita Chapter 2, Verse 47 teach about action?"
        )
        self.assertEqual(analysis.status, "pending_review")

        # Submit substantive approval
        updated_rec = self.unified_engine.review_report(
            report_id=analysis.report_id,
            decision="approved",
            reviewer="Dr. S. Radhakrishnan (Lead Philologist)",
            notes="Scholarly review verifies authentic Niṣkāma Karma synthesis and valid source citations.",
        )
        self.assertEqual(updated_rec.status, "approved")
        self.assertIsNotNone(updated_rec.approved_hash)

    # 13. Publishing without authorization is blocked
    def test_13_publishing_without_authorization_is_blocked(self) -> None:
        """Requirement 13: Publishing an unapproved or unauthorized report raises UnauthorizedPublishingError."""
        brief, analysis, unified = self.unified_engine.process(
            "What does Gita Chapter 2, Verse 47 teach?"
        )
        # Attempting to publish while in pending_review raises UnauthorizedPublishingError
        with self.assertRaises(UnauthorizedPublishingError):
            self.unified_engine.publish_report(report_id=analysis.report_id)

    # 14. Complete end-to-end question processing
    def test_14_complete_end_to_end_question_processing(self) -> None:
        """Requirement 14: End-to-end question processing from prompt to verified publication."""
        # Step A: Process inquiry
        brief, analysis, unified = self.unified_engine.process(
            "What does Bhagavad Gita Chapter 2, Verse 47 teach and how does it compare with procrastination research?"
        )
        self.assertIsInstance(unified, UnifiedResponse)
        self.assertEqual(unified.governance_status, "pending_review")

        # Step B: Human Review & Approval
        self.unified_engine.review_report(
            report_id=analysis.report_id,
            decision="approved",
            reviewer="Dr. S. Radhakrishnan",
            notes="Scholarly review confirms Niṣkāma Karma synthesis and valid comparative methodology.",
        )

        # Step C: Publication Authorization
        self.unified_engine.authorize_publication(
            report_id=analysis.report_id,
            authorizer="Editorial Board Director",
            channel="local_file",
            notes="Authorized for publication as primary comparative research brief.",
        )

        # Step D: Publication via LocalFilePublisher
        pub_record = self.unified_engine.publish_report(
            report_id=analysis.report_id,
            channel="local_file",
        )
        self.assertEqual(pub_record.status, "published")
        self.assertIsNotNone(pub_record.published_at_utc)


if __name__ == "__main__":
    unittest.main()
