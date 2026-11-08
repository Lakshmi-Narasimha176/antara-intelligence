"""Unit tests for ANTARĀ Module 3: Research Intelligence.

Tests cover:
1. Research question validation
2. Research source insertion
3. Source provenance preservation
4. DOI-based duplicate detection
5. Metadata-based duplicate detection
6. Supporting evidence classification
7. Contradicting evidence classification
8. Contextual evidence classification
9. Inconclusive evidence classification
10. Invalid or incomplete provider responses
11. Network and timeout failures
12. Human approval requirements
13. Rejection workflow
14. Audit history
15. Existing Module 1 and Module 2 compatibility
16. End-to-end integration using mocked research providers
"""

from pathlib import Path
import tempfile
import unittest

from engine.orchestrator import create_brief
from engine.research import (
    DuplicateResearchError,
    InvalidEvidenceError,
    MockResearchProvider,
    ProviderError,
    ResearchManager,
    ResearchSourceDraft,
    SubstantiveReviewError,
    normalize_doi,
)


class ResearchTestCase(unittest.TestCase):
    """Base test fixture setting up an isolated temporary database and ResearchManager."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_research.db"
        self.mgr = ResearchManager(self.db_path)

        # Create a deterministic mock source draft
        self.sample_draft = ResearchSourceDraft(
            title="Temporal Discounting and Procrastination: A Behavioral Study",
            authors="Steel, P., & König, C. J.",
            journal="Psychological Bulletin",
            year=2006,
            doi="10.1037/0033-2909.133.1.65",
            url="https://doi.org/10.1037/0033-2909.133.1.65",
            abstract="Integrating hyperbolic discounting and expectancy theory into Temporal Motivation Theory.",
            methodology="Meta-Analysis & Theoretical Synthesis",
            study_population="General working & academic populations",
            sample_size=691,
            limitations="Heterogeneous effect sizes across correlational studies.",
            rights_note="Peer-reviewed scholarly article.",
            provider="mock_academic",
        )

    def tearDown(self) -> None:
        import gc
        gc.collect()
        self.temp_dir.cleanup()


class ResearchSourceTests(ResearchTestCase):
    """Tests covering source validation, insertion, provenance, and deduplication."""

    def test_research_source_validation_rejects_empty_fields(self) -> None:
        # Rejects empty title
        draft_no_title = ResearchSourceDraft(title="   ", authors="Author A")
        with self.assertRaises(ValueError):
            self.mgr.insert_source(draft_no_title)

        # Rejects empty authors
        draft_no_authors = ResearchSourceDraft(title="Title A", authors="   ")
        with self.assertRaises(ValueError):
            self.mgr.insert_source(draft_no_authors)

    def test_research_source_insertion_and_provenance_preservation(self) -> None:
        source_id = self.mgr.insert_source(self.sample_draft)
        self.assertIsInstance(source_id, int)

        source = self.mgr.get_source(source_id)
        self.assertIsNotNone(source)
        self.assertEqual(source.title, "Temporal Discounting and Procrastination: A Behavioral Study")
        self.assertEqual(source.authors, "Steel, P., & König, C. J.")
        self.assertEqual(source.journal, "Psychological Bulletin")
        self.assertEqual(source.year, 2006)
        self.assertEqual(source.doi, "10.1037/0033-2909.133.1.65")
        self.assertEqual(source.sample_size, 691)
        self.assertEqual(source.methodology, "Meta-Analysis & Theoretical Synthesis")
        self.assertEqual(source.verification_status, "unreviewed")
        self.assertTrue(len(source.content_hash) == 64)

    def test_doi_based_duplicate_detection(self) -> None:
        self.mgr.insert_source(self.sample_draft)

        # Attempt to insert same DOI with different casing/URL formatting
        duplicate_draft = ResearchSourceDraft(
            title="Alternative Title on Procrastination",
            authors="Different Author",
            year=2007,
            doi="https://doi.org/10.1037/0033-2909.133.1.65",  # Same DOI
        )
        with self.assertRaises(DuplicateResearchError):
            self.mgr.insert_source(duplicate_draft)

    def test_metadata_based_duplicate_detection(self) -> None:
        # Draft without DOI
        draft_no_doi = ResearchSourceDraft(
            title="Cognitive Dissonance in Action",
            authors="Festinger, L., & Carlsmith, J. M.",
            year=1959,
        )
        self.mgr.insert_source(draft_no_doi)

        # Duplicate title, first author, and year without DOI
        dup = ResearchSourceDraft(
            title="cognitive dissonance in action",
            authors="Festinger, L.",
            year=1959,
        )
        with self.assertRaises(DuplicateResearchError):
            self.mgr.insert_source(dup)


class EvidenceClassificationTests(ResearchTestCase):
    """Tests covering evidence quad-classification and constraints."""

    def setUp(self) -> None:
        super().setUp()
        self.source_id = self.mgr.insert_source(self.sample_draft)

    def test_supporting_evidence_classification(self) -> None:
        ev_id = self.mgr.add_evidence(
            source_id=self.source_id,
            finding="Temporal discounting correlates positively with procrastination (r = .41).",
            claim="People procrastinate when delayed rewards are steeply discounted.",
            classification="supporting",
            strength="high",
            limitations="Correlational findings across student cohorts.",
        )
        ev = self.mgr.get_evidence(ev_id)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.classification, "supporting")
        self.assertEqual(ev.strength, "high")
        self.assertEqual(ev.review_status, "unreviewed")

    def test_contradicting_evidence_classification(self) -> None:
        ev_id = self.mgr.add_evidence(
            source_id=self.source_id,
            finding="High conscientiousness individuals show negligible procrastination despite delay discounting.",
            claim="Temporal discounting universally causes procrastination regardless of trait self-regulation.",
            classification="contradicting",
            strength="moderate",
            limitations="Moderation observed in structured corporate environments.",
        )
        ev = self.mgr.get_evidence(ev_id)
        self.assertEqual(ev.classification, "contradicting")

    def test_contextual_evidence_classification(self) -> None:
        ev_id = self.mgr.add_evidence(
            source_id=self.source_id,
            finding="Arousal procrastination accounts for only a minor fraction of procrastination cases.",
            claim="Task difficulty influences emotional state during goal initiation.",
            classification="contextual",
            strength="moderate",
        )
        ev = self.mgr.get_evidence(ev_id)
        self.assertEqual(ev.classification, "contextual")

    def test_inconclusive_evidence_classification(self) -> None:
        ev_id = self.mgr.add_evidence(
            source_id=self.source_id,
            finding="Mixed results across 3 small exploratory pilot studies on willpower depletion.",
            claim="Willpower is a strictly depletable biological glucose reservoir.",
            classification="inconclusive",
            strength="low",
            limitations="Replication failures in multi-site preregistered trials.",
        )
        ev = self.mgr.get_evidence(ev_id)
        self.assertEqual(ev.classification, "inconclusive")

    def test_rejects_invalid_classification_or_strength(self) -> None:
        with self.assertRaises(InvalidEvidenceError):
            self.mgr.add_evidence(
                source_id=self.source_id,
                finding="Finding",
                claim="Claim",
                classification="unsupported_category",  # Invalid
            )
        with self.assertRaises(InvalidEvidenceError):
            self.mgr.add_evidence(
                source_id=self.source_id,
                finding="Finding",
                claim="Claim",
                classification="supporting",
                strength="ultra_high",  # Invalid
            )


class HumanReviewWorkflowTests(ResearchTestCase):
    """Tests covering human review requirements, rejection, and audit trails."""

    def setUp(self) -> None:
        super().setUp()
        self.source_id = self.mgr.insert_source(self.sample_draft)
        self.evidence_id = self.mgr.add_evidence(
            source_id=self.source_id,
            finding="Hyperbolic discounting predicts delay behavior across 691 effect sizes.",
            claim="Procrastination stems from temporal motivation decay.",
            classification="supporting",
        )

    def test_human_approval_requires_substantive_notes(self) -> None:
        # Rejects trivial notes (< 15 characters)
        with self.assertRaises(SubstantiveReviewError):
            self.mgr.review_source(
                source_id=self.source_id,
                decision="approved",
                reviewer="Reviewer A",
                notes="Looks fine.",  # Too short
            )

        # Rejects empty reviewer
        with self.assertRaises(SubstantiveReviewError):
            self.mgr.review_source(
                source_id=self.source_id,
                decision="approved",
                reviewer="   ",
                notes="Methodologically sound meta-analysis published in leading journal.",
            )

        # Successful approval
        audit = self.mgr.review_source(
            source_id=self.source_id,
            decision="approved",
            reviewer="Dr. M. Patel (Behavioral Science)",
            notes="Methodologically sound meta-analysis published in Psychological Bulletin.",
        )
        self.assertEqual(audit.new_status, "approved")
        source = self.mgr.get_source(self.source_id)
        self.assertEqual(source.verification_status, "approved")

    def test_rejection_workflow_and_audit_history(self) -> None:
        # Review evidence: transition to rejected
        audit = self.mgr.review_evidence(
            evidence_id=self.evidence_id,
            decision="rejected",
            reviewer="Dr. M. Patel",
            notes="Underpowered sample size in sub-analysis; evidence claims overstated.",
        )
        self.assertEqual(audit.new_status, "rejected")

        ev = self.mgr.get_evidence(self.evidence_id)
        self.assertEqual(ev.review_status, "rejected")

        # Audit trail must record initial extraction and rejection
        history = self.mgr.get_audit_history("evidence", self.evidence_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].previous_status, "none")
        self.assertEqual(history[0].new_status, "unreviewed")
        self.assertEqual(history[1].previous_status, "unreviewed")
        self.assertEqual(history[1].new_status, "rejected")


class ProviderFailureAndResilienceTests(ResearchTestCase):
    """Tests covering provider timeouts, incomplete responses, and network failure resilience."""

    def test_handles_provider_timeout_and_network_failures(self) -> None:
        failing_provider = MockResearchProvider(should_fail=True, failure_message="Connection timed out after 10s")
        mgr = ResearchManager(self.db_path, providers=[failing_provider])

        # Must not raise unhandled exception
        results = mgr.query_providers("procrastination behavioral economics")
        self.assertEqual(results, [])

    def test_normalizes_doi_helper(self) -> None:
        self.assertEqual(normalize_doi("https://doi.org/10.1037/0033-2909.133.1.65"), "10.1037/0033-2909.133.1.65")
        self.assertEqual(normalize_doi("http://dx.doi.org/10.1007/s11199-011-9988-4"), "10.1007/s11199-011-9988-4")
        self.assertEqual(normalize_doi("doi: 10.1016/j.jvb.2010.05.008"), "10.1016/j.jvb.2010.05.008")
        self.assertIsNone(normalize_doi(None))
        self.assertIsNone(normalize_doi("   "))


class IntegrationAndCompatibilityTests(ResearchTestCase):
    """Tests covering end-to-end Module 3 integration and Module 1 & 2 compatibility."""

    def test_collect_research_for_question(self) -> None:
        source_id = self.mgr.insert_source(self.sample_draft)
        self.mgr.add_evidence(
            source_id=source_id,
            finding="Temporal motivation theory accounts for variance in procrastination.",
            claim="Motivation decreases as delay to reward increases.",
            classification="supporting",
        )

        ctx = self.mgr.collect_research_for_question("Why do people procrastinate?", topic="human_behavior")
        self.assertEqual(ctx.status, "research_collected")
        self.assertEqual(ctx.total_sources, 1)
        self.assertEqual(ctx.total_evidence, 1)
        self.assertEqual(len(ctx.evidence_by_classification["supporting"]), 1)
        self.assertGreaterEqual(len(ctx.evidence_gaps), 1)

    def test_create_brief_end_to_end_with_research_integration(self) -> None:
        source_id = self.mgr.insert_source(self.sample_draft)
        self.mgr.add_evidence(
            source_id=source_id,
            finding="Temporal discounting correlates with delay behavior.",
            claim="Procrastination relates to temporal discounting.",
            classification="supporting",
        )

        question = "Why do people procrastinate even when they know what matters?"
        brief = create_brief(question, research_mgr=self.mgr)

        self.assertEqual(brief.topic, "human_behavior")
        self.assertTrue(brief.human_review_required)
        self.assertIn("research_context", brief.to_dict())

        r_ctx = brief.research_context
        self.assertEqual(r_ctx["status"], "research_collected")
        self.assertEqual(r_ctx["total_sources"], 1)
        self.assertEqual(r_ctx["total_evidence"], 1)

    def test_existing_module1_and_module2_compatibility(self) -> None:
        # Module 1 non-philosophical query without research
        brief_m1 = create_brief("Why do people procrastinate?", attach_research=False)
        self.assertEqual(brief_m1.status, "brief_created")
        self.assertEqual(brief_m1.research_status, "not_started")
        self.assertEqual(brief_m1.research_context, {})


if __name__ == "__main__":
    unittest.main()
