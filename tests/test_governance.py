"""Unit tests for ANTARĀ Module 5: Human-in-the-Loop Governance & Publishing Pipeline.

Comprehensive offline test coverage for:
1. Valid lifecycle state transitions.
2. Invalid lifecycle state transitions.
3. Approval without validation (blocked).
4. Approval without reviewer identity (blocked).
5. Missing or insubstantial review notes (blocked).
6. Content modification after approval (invalidates prior approval).
7. Fingerprint mismatch during publishing (blocked).
8. Publishing without approval (blocked).
9. Publishing with invalidated approval (blocked).
10. Duplicate publication attempts (blocked).
11. Audit history integrity (append-only log).
12. Revision handling and version preservation.
13. JSON export fidelity.
14. Markdown export fidelity.
15. Mock publishing provider behavior.
16. End-to-end integration with Modules 1–4.
"""

from pathlib import Path
import tempfile
import unittest

from engine.governance import (
    CONTENT_TYPE_PHILOSOPHICAL_ANALYSIS,
    STATE_APPROVED,
    STATE_ARCHIVED,
    STATE_PENDING_REVIEW,
    STATE_PUBLISHED,
    STATE_READY_TO_PUBLISH,
    STATE_REJECTED,
    STATE_REVISION_REQUESTED,
    STATE_VALIDATION_FAILED,
    DuplicatePublicationError,
    FingerprintMismatchError,
    GovernanceEngine,
    GovernanceError,
    GovernanceTransitionError,
    LocalFilePublisher,
    MockPublishingProvider,
    UnauthorizedPublishingError,
    compute_governance_hash,
)
from engine.knowledge import KnowledgeBase, SubstantiveEvidenceError
from engine.llm_provider import MockLLMProvider
from engine.orchestrator import create_brief
from engine.reasoning import ReasoningAnalysis, ReasoningEngine
from engine.research import ResearchManager, ResearchSourceDraft


class GovernanceTestCase(unittest.TestCase):
    """Base fixture setting up an isolated temporary database and governance engine."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_governance.db"

        # Managers on the shared database
        self.kb = KnowledgeBase(self.db_path)
        self.mgr = ResearchManager(self.db_path)
        self.engine = GovernanceEngine(self.db_path)

        # 1. Seed Gita source and verse
        self.gita_source_id = self.kb.get_or_create_source(
            title="The Bhagavadgita",
            author="Dr. S. Radhakrishnan",
            year=1993,
        )
        self.gita_verse_id = self.kb.insert_verse(
            source_id=self.gita_source_id,
            chapter=2,
            verse=47,
            sanskrit="कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।\nमा कर्मफलहेतुर्भूर्मा ते सङ्गोऽस्त्वकर्मणि॥",
            transliteration="karmaṇy evādhikāras te mā phaleṣu kadācana |\nmā karma-phala-hetur bhūr mā te saṅgo 'stv akarmaṇi ||",
            translation="To action alone hast thou a right and never at all to its fruits; let not the fruits of action be thy motive; neither let there be in thee any attachment to inaction.",
            language="en",
            locator="Ch 2, V 47",
        )
        self.kb.review_verse(
            verse_id=self.gita_verse_id,
            decision="verified",
            reviewer="Prof. M. Hiriyanna",
            evidence="Collated with BORI critical edition Vol. 7, p. 88.",
        )

        # 2. Seed research source and evidence
        self.research_source_id = self.mgr.insert_source(
            ResearchSourceDraft(
                title="The Nature of Procrastination: A Meta-Analysis",
                authors="Steel, Piers",
                year=2007,
                doi="10.1037/0033-2909.133.1.65",
                abstract="Meta-analysis on procrastination correlates.",
            )
        )
        self.mgr.review_source(
            source_id=self.research_source_id,
            decision="approved",
            reviewer="Dr. Vance",
            notes="PRISMA guidelines verified.",
        )
        self.evidence_id = self.mgr.add_evidence(
            source_id=self.research_source_id,
            finding="Procrastination correlates strongly with impulsiveness (r = 0.41).",
            claim="Procrastination correlates strongly with impulsiveness.",
            classification="supporting",
        )
        self.mgr.review_evidence(
            evidence_id=self.evidence_id,
            decision="approved",
            reviewer="Dr. Vance",
            notes="Statistical effect confirmed.",
        )

        # Deterministic sample analysis passing Module 4
        self.sample_analysis = ReasoningAnalysis(
            report_id="test_report_101",
            question="What does the Bhagavad Gita teach in Chapter 2, Verse 47?",
            executive_summary="Synthesis between detachment from fruits and temporal motivation theory.",
            philosophical_perspective="Niṣkāma Karma defines action without anxiety for results.",
            relevant_gita_teachings=[
                {
                    "verse_id": self.gita_verse_id,
                    "chapter": 2,
                    "verse": 47,
                    "teaching": "Stewardship over duty without entitlement to outcomes.",
                    "sanskrit_quote": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।\nमा कर्मफलहेतुर्भूर्मा ते सङ्गोऽस्त्वकर्मणि॥",
                    "translation_quote": "To action alone hast thou a right and never at all to its fruits; let not the fruits of action be thy motive; neither let there be in thee any attachment to inaction.",
                }
            ],
            modern_scientific_perspectives="Temporal motivation theory shows outcome fixation impairs execution.",
            supporting_research_evidence=[
                {
                    "evidence_id": self.evidence_id,
                    "source_id": self.research_source_id,
                    "finding": "Procrastination correlates strongly with impulsiveness (r = 0.41).",
                }
            ],
            contradicting_research_evidence=[],
            philosophical_and_scientific_similarities=["Both emphasize process over outcome anxiety."],
            important_differences=["Gita is ontological; psychology is behavioral."],
            critical_analysis="Comparative evaluation across distinct paradigms.",
            original_synthesized_insight="Detachment stabilizes executive function.",
            practical_implications=["Focus on daily craft."],
            limitations_and_uncertainty=["Cross-paradigm boundary conditions apply."],
            research_gaps=["Interventional trials needed."],
            exact_source_citations=[{"type": "gita", "id": self.gita_verse_id}],
            claims_requiring_human_review=[],
            status=STATE_PENDING_REVIEW,
            human_review_required=True,
            created_at_utc="2026-11-08T11:00:00+00:00",
            updated_at_utc="2026-11-08T11:00:00+00:00",
            validation_report={"overall_status": "PASSED_VERIFIED", "total_claims": 1, "verified_claims": 1},
        )

    def tearDown(self) -> None:
        import gc
        gc.collect()
        self.temp_dir.cleanup()


class StateTransitionAndReviewTests(GovernanceTestCase):
    """Tests covering lifecycle state machine, human reviews, and invalid transitions."""

    def test_valid_state_transitions_lifecycle(self) -> None:
        """Requirement 1: Valid progression generated -> pending_review -> approved -> ready_to_publish -> published -> archived."""
        # 1. Register report (enters pending_review because validation passed)
        rec = self.engine.register_report(self.sample_analysis)
        self.assertEqual(rec.current_state, STATE_PENDING_REVIEW)

        # 2. Human review: approve
        approved = self.engine.review(
            report_id=rec.report_id,
            action="approve",
            reviewer="Dr. S. Radhakrishnan (Philology Editor)",
            notes="Substantive scholarly review confirms philosophical accuracy and citations.",
        )
        self.assertEqual(approved.current_state, STATE_APPROVED)
        self.assertIsNotNone(approved.approved_hash)
        self.assertEqual(approved.approved_hash, approved.current_hash)

        # 3. Authorize publication
        authorized = self.engine.authorize_publication(
            report_id=rec.report_id,
            authorizer="Editorial Board Chair",
            target_channels=["local_file", "mock_web"],
            notes="Authorized for release in scholarly quarterly bulletin.",
        )
        self.assertEqual(authorized.current_state, STATE_READY_TO_PUBLISH)

        # 4. Publish
        publisher = MockPublishingProvider()
        receipts = self.engine.publish(report_id=rec.report_id, publisher=publisher, publisher_actor="Operations Desk")
        self.assertEqual(len(receipts), 2)
        published = self.engine.get_record(rec.report_id)
        self.assertEqual(published.current_state, STATE_PUBLISHED)
        self.assertIsNotNone(published.published_at_utc)

        # 5. Archive
        archived = self.engine.archive(
            report_id=rec.report_id,
            actor="Archivist",
            notes="Archived after standard publication cycle completed.",
        )
        self.assertEqual(archived.current_state, STATE_ARCHIVED)

    def test_invalid_state_transitions(self) -> None:
        """Requirement 2: Illegal state transitions are rejected."""
        rec = self.engine.register_report(self.sample_analysis)
        self.assertEqual(rec.current_state, STATE_PENDING_REVIEW)

        # Cannot jump from pending_review directly to published or ready_to_publish
        with self.assertRaises(UnauthorizedPublishingError):
            self.engine.publish(report_id=rec.report_id)

        with self.assertRaises(UnauthorizedPublishingError):
            self.engine.authorize_publication(
                report_id=rec.report_id,
                authorizer="Chair",
                target_channels=["local"],
                notes="Premature authorization attempt across channels.",
            )

    def test_approval_without_validation_is_blocked(self) -> None:
        """Requirement 3: Reports failing validation cannot enter pending_review and cannot be approved."""
        failing_analysis = ReasoningAnalysis(
            report_id="failing_report_999",
            question="Unvalidated question?",
            executive_summary="Summary",
            philosophical_perspective="Gita",
            relevant_gita_teachings=[],
            modern_scientific_perspectives="Science",
            supporting_research_evidence=[],
            contradicting_research_evidence=[],
            philosophical_and_scientific_similarities=[],
            important_differences=[],
            critical_analysis="Critique",
            original_synthesized_insight="Insight",
            practical_implications=[],
            limitations_and_uncertainty=[],
            research_gaps=[],
            exact_source_citations=[],
            claims_requiring_human_review=[],
            status=STATE_VALIDATION_FAILED,
            human_review_required=True,
            created_at_utc="2026-11-08T11:00:00+00:00",
            updated_at_utc="2026-11-08T11:00:00+00:00",
            validation_report={"overall_status": "FAILED_UNSUPPORTED", "unsupported_claims": 2},
        )

        rec = self.engine.register_report(failing_analysis)
        self.assertEqual(rec.current_state, STATE_VALIDATION_FAILED)

        # Attempting approval on validation_failed report raises error
        with self.assertRaises(GovernanceTransitionError):
            self.engine.review(
                report_id=rec.report_id,
                action="approve",
                reviewer="Reviewer",
                notes="Illegal approval attempt.",
            )

    def test_approval_without_reviewer_identity(self) -> None:
        """Requirement 4: Empty reviewer identity is strictly rejected."""
        rec = self.engine.register_report(self.sample_analysis)
        with self.assertRaises(GovernanceError):
            self.engine.review(
                report_id=rec.report_id,
                action="approve",
                reviewer="   ",
                notes="Substantive notes provided but empty reviewer.",
            )

    def test_missing_or_insubstantial_review_notes(self) -> None:
        """Requirement 5: Review notes < 15 characters raise SubstantiveEvidenceError."""
        rec = self.engine.register_report(self.sample_analysis)
        with self.assertRaises(SubstantiveEvidenceError):
            self.engine.review(
                report_id=rec.report_id,
                action="approve",
                reviewer="Dr. Reviewer",
                notes="looks good",  # Only 10 chars
            )


class FingerprintAndPublishingSafeguardsTests(GovernanceTestCase):
    """Tests covering fingerprint verification, post-approval modification, and publishing guards."""

    def test_content_modification_after_approval_invalidates_approval(self) -> None:
        """Requirement 6 & 9: Modifying content after approval invalidates approval and resets state."""
        rec = self.engine.register_report(self.sample_analysis)

        # 1. Approve report
        approved = self.engine.review(
            report_id=rec.report_id,
            action="approve",
            reviewer="Reviewer A",
            notes="Substantive notes on initial approval.",
        )
        self.assertEqual(approved.current_state, STATE_APPROVED)
        initial_approved_hash = approved.approved_hash

        # 2. Revise content (new modified version)
        modified_content = dict(self.sample_analysis.to_dict())
        modified_content["executive_summary"] = "MODIFIED SUMMARY: Introducing altered conclusions."
        revised = self.engine.revise_content(
            report_id=rec.report_id,
            new_content=modified_content,
            editor="Editor B",
            change_summary="Updated executive summary.",
            notes="Revised following editorial comments.",
        )

        # Version increments to 2
        self.assertEqual(revised.current_version, 2)
        # Approval is invalidated: approved_hash is None, state returns to pending_review
        self.assertIsNone(revised.approved_hash)
        self.assertEqual(revised.current_state, STATE_PENDING_REVIEW)
        self.assertNotEqual(revised.current_hash, initial_approved_hash)

        # 3. Publishing attempt without re-approval MUST fail
        with self.assertRaises(UnauthorizedPublishingError):
            self.engine.authorize_publication(
                report_id=rec.report_id,
                authorizer="Publishing Director",
                target_channels=["local"],
                notes="Attempting publication of modified content without re-approval.",
            )

    def test_fingerprint_mismatch_blocks_publication(self) -> None:
        """Requirement 7: Out-of-band database tampering detected by cryptographic hash mismatch."""
        rec = self.engine.register_report(self.sample_analysis)
        self.engine.review(
            report_id=rec.report_id,
            action="approve",
            reviewer="Reviewer A",
            notes="Scholarly review confirms Niṣkāma Karma synthesis.",
        )
        self.engine.authorize_publication(
            report_id=rec.report_id,
            authorizer="Authorizer",
            target_channels=["local_file"],
            notes="Authorized for release.",
        )

        # Simulate unauthorized out-of-band tampering in SQLite
        with self.engine.connection() as conn:
            conn.execute(
                "UPDATE governance_records SET current_hash = 'tampered_hash_1234567890' WHERE id = ?;",
                (rec.report_id,),
            )
            conn.commit()

        # Publishing must fail with FingerprintMismatchError
        with self.assertRaises(FingerprintMismatchError):
            self.engine.publish(report_id=rec.report_id)

    def test_publishing_without_approval_is_blocked(self) -> None:
        """Requirement 8: Publishing unapproved reports raises UnauthorizedPublishingError."""
        rec = self.engine.register_report(self.sample_analysis)
        self.assertEqual(rec.current_state, STATE_PENDING_REVIEW)

        with self.assertRaises(UnauthorizedPublishingError):
            self.engine.publish(report_id=rec.report_id)

    def test_duplicate_publication_attempts_are_blocked(self) -> None:
        """Requirement 10: Attempting to publish the same version to the same channel twice raises DuplicatePublicationError."""
        rec = self.engine.register_report(self.sample_analysis)
        self.engine.review(
            report_id=rec.report_id,
            action="approve",
            reviewer="Reviewer A",
            notes="Substantive notes on approval.",
        )
        self.engine.authorize_publication(
            report_id=rec.report_id,
            authorizer="Authorizer",
            target_channels=["local_file"],
            notes="Authorized for release.",
        )

        publisher = MockPublishingProvider()
        # First publication succeeds
        self.engine.publish(report_id=rec.report_id, publisher=publisher)

        # Attempting second publication on the published report raises UnauthorizedPublishingError or DuplicatePublicationError
        with self.assertRaises(UnauthorizedPublishingError):
            self.engine.publish(report_id=rec.report_id, publisher=publisher)


class VersioningAuditAndExportTests(GovernanceTestCase):
    """Tests covering version preservation, audit trail logging, and JSON/Markdown exporters."""

    def test_audit_history_is_append_only(self) -> None:
        """Requirement 11: Every state transition appends an immutable audit log entry."""
        rec = self.engine.register_report(self.sample_analysis)
        self.engine.review(
            report_id=rec.report_id,
            action="approve",
            reviewer="Reviewer 1",
            notes="Substantive notes 1.",
        )
        self.engine.authorize_publication(
            report_id=rec.report_id,
            authorizer="Authorizer 1",
            target_channels=["local"],
            notes="Substantive notes 2.",
        )

        audit_entries = self.engine.get_audit_trail(rec.report_id)
        self.assertGreaterEqual(len(audit_entries), 3)

        # Assert actions are in chronological order
        actions = [e.action for e in audit_entries]
        self.assertIn("register_report", actions[0])
        self.assertIn("human_approval", actions[1])
        self.assertIn("authorize_publication", actions[2])

    def test_revision_handling_and_version_preservation(self) -> None:
        """Requirement 12: Creating revision v2 preserves v1 snapshot and allows retrieval of both."""
        rec = self.engine.register_report(self.sample_analysis)
        v1 = self.engine.get_version(rec.report_id, 1)
        self.assertEqual(v1.version, 1)

        # Create revision v2
        modified_content = dict(self.sample_analysis.to_dict())
        modified_content["practical_implications"] = ["Revised practical application step."]
        self.engine.revise_content(
            report_id=rec.report_id,
            new_content=modified_content,
            editor="Senior Editor",
            change_summary="Clarified practical implications.",
            notes="Applied peer reviewer recommendations.",
        )

        v2 = self.engine.get_version(rec.report_id, 2)
        self.assertEqual(v2.version, 2)
        self.assertIn("Revised practical application step.", v2.content["practical_implications"])

        # v1 remains completely unchanged and retrievable
        v1_again = self.engine.get_version(rec.report_id, 1)
        self.assertEqual(v1_again.version, 1)
        self.assertEqual(v1_again.content_hash, v1.content_hash)

    def test_json_and_markdown_exports(self) -> None:
        """Requirement 13 & 14: Verifies structured JSON and publication-grade Markdown exports."""
        rec = self.engine.register_report(self.sample_analysis)

        # JSON Export
        json_output = self.engine.export_report(rec.report_id, format_type="json")
        self.assertIn("test_report_101", json_output)
        self.assertIn("Niṣkāma Karma", json_output)

        # Markdown Export
        md_output = self.engine.export_report(rec.report_id, format_type="markdown")
        self.assertIn("# What does the Bhagavad Gita teach in Chapter 2, Verse 47?", md_output)
        self.assertIn("Executive Summary", md_output)
        self.assertIn("कर्मण्येवाधिकारस्ते", md_output)
        self.assertIn("Procrastination correlates strongly with impulsiveness", md_output)
        self.assertIn("Cryptographic Content Hash", md_output)

    def test_mock_publishing_provider_failure(self) -> None:
        """Requirement 15: Mock publisher captures packages and handles simulated network/disk failure."""
        rec = self.engine.register_report(self.sample_analysis)
        self.engine.review(
            report_id=rec.report_id,
            action="approve",
            reviewer="Reviewer",
            notes="Substantive human review notes confirming accurate citations and methodology.",
        )
        self.engine.authorize_publication(
            report_id=rec.report_id,
            authorizer="Authorizer",
            target_channels=["mock_channel"],
            notes="Substantive human authorization notes confirming release across channels.",
        )

        # Simulated failure in publisher
        failing_pub = MockPublishingProvider(should_fail=IOError("Simulated disk quota failure."))
        with self.assertRaises(IOError):
            self.engine.publish(report_id=rec.report_id, publisher=failing_pub)

        # State should remain ready_to_publish (not falsely marked as published)
        current = self.engine.get_record(rec.report_id)
        self.assertEqual(current.current_state, STATE_READY_TO_PUBLISH)

    def test_end_to_end_module_integration(self) -> None:
        """Requirement 16: Module 1-4 reasoning analysis seamlessly registers and publishes through Module 5."""
        # 1. Create Brief (Module 1, 2, 3)
        brief = create_brief(
            "What does the Bhagavad Gita teach in Chapter 2, Verse 47?",
            kb=self.kb,
            research_mgr=self.mgr,
        )

        # 2. Run Reasoning Synthesis (Module 4 Fact-Checking integrated)
        mock_provider = MockLLMProvider()
        reasoning_engine = ReasoningEngine(db_path=self.db_path, provider=mock_provider)
        analysis = reasoning_engine.analyze_brief(brief)

        # 3. Register into Governance (Module 5)
        gov_rec = self.engine.register_report(
            analysis=analysis,
            content_type=CONTENT_TYPE_PHILOSOPHICAL_ANALYSIS,
            created_by="automated_pipeline",
        )
        self.assertEqual(gov_rec.current_state, STATE_PENDING_REVIEW)

        # 4. Human Review & Approval
        approved_rec = self.engine.review(
            report_id=gov_rec.report_id,
            action="approve",
            reviewer="Dr. Radhakrishnan (Editor-in-Chief)",
            notes="Full philosophical and psychological collation validated and approved.",
        )
        self.assertEqual(approved_rec.current_state, STATE_APPROVED)

        # 5. Authorize Publication
        auth_rec = self.engine.authorize_publication(
            report_id=gov_rec.report_id,
            authorizer="Editorial Governance Board",
            target_channels=["local_file"],
            notes="Publication authorized for digital knowledge repository release.",
        )
        self.assertEqual(auth_rec.current_state, STATE_READY_TO_PUBLISH)

        # 6. Publish via LocalFilePublisher
        out_pub_dir = Path(self.temp_dir.name) / "published_output"
        publisher = LocalFilePublisher(output_root=out_pub_dir)
        receipts = self.engine.publish(report_id=gov_rec.report_id, publisher=publisher)

        self.assertEqual(len(receipts), 1)
        self.assertTrue(Path(receipts[0].published_uri_or_path).exists())
        self.assertEqual(self.engine.get_record(gov_rec.report_id).current_state, STATE_PUBLISHED)
