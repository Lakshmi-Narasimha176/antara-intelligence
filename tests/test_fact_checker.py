"""Unit tests for ANTARĀ Module 4: Anti-Hallucination & Fact-Checking Engine.

Comprehensive offline tests covering:
1. Valid source references (Gītā and research).
2. Missing source references.
3. Unverified Gītā records.
4. Tampered Gītā records (cryptographic hash mismatch).
5. Exact quotation matching (Sanskrit, transliteration, English, research).
6. Incorrect quotations.
7. Approved research evidence.
8. Rejected research evidence.
9. Unsupported claims (nonexistent IDs, fabricated DOIs).
10. Contradicting evidence.
11. Missing citations.
12. Invalid input schemas.
13. Empty evidence collections.
14. Database failures.
15. Integration compatibility with Modules 1, 2, and 3.
16. Validation report generation and schema stability.
"""

from pathlib import Path
import tempfile
import unittest

from engine.fact_checker import (
    STATUS_CONTRADICTED,
    STATUS_INSUFFICIENT_EVIDENCE,
    STATUS_PARTIALLY_SUPPORTED,
    STATUS_REQUIRES_HUMAN_REVIEW,
    STATUS_SOURCE_VERIFIED,
    STATUS_UNSUPPORTED,
    Claim,
    ClaimValidationError,
    FactChecker,
    validate_brief_claims,
)
from engine.knowledge import KnowledgeBase
from engine.orchestrator import create_brief
from engine.research import ResearchManager, ResearchSourceDraft


class FactCheckerTestCase(unittest.TestCase):
    """Base fixture creating an isolated SQLite database with Gita and Research fixtures."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_fact_checker.db"

        # Initialize Knowledge and Research managers on the same test database
        self.kb = KnowledgeBase(self.db_path)
        self.mgr = ResearchManager(self.db_path)
        self.checker = FactChecker(self.db_path)

        # 1. Seed authenticated Gita source and verse
        self.gita_source_id = self.kb.get_or_create_source(
            title="The Bhagavadgita: With Text, Translation and Notes",
            author="Dr. S. Radhakrishnan",
            translator="Dr. S. Radhakrishnan",
            edition="HarperCollins 1993",
            year=1993,
            url="https://archive.org/details/the-bhagavadgita-radhakrishnan",
            rights_note="Public research commentary under scholarly fair dealing.",
        )
        self.gita_verse_id = self.kb.insert_verse(
            source_id=self.gita_source_id,
            chapter=2,
            verse=47,
            sanskrit="कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।\nमा कर्मफलहेतुर्भूर्मा ते सङ्गोऽस्त्वकर्मणि॥",
            transliteration="karmaṇy evādhikāras te mā phaleṣu kadācana |\nmā karma-phala-hetur bhūr mā te saṅgo 'stv akarmaṇi ||",
            translation="To action alone hast thou a right and never at all to its fruits; let not the fruits of action be thy motive; neither let there be in thee any attachment to inaction.",
            language="en",
            locator="Chapter 2, Verse 47, p. 119",
            notes="Foundational formulation of Niṣkāma Karma (action without desire for fruits).",
        )

        # 2. Seed academic research source and evidence
        draft = ResearchSourceDraft(
            title="The Nature of Procrastination: A Meta-Analytic Review",
            authors="Steel, Piers",
            journal="Psychological Bulletin",
            year=2007,
            doi="10.1037/0033-2909.133.1.65",
            url="https://doi.org/10.1037/0033-2909.133.1.65",
            abstract="Meta-analysis synthesizing correlates of procrastination across 212 samples.",
            methodology="Meta-analysis synthesizing 691 correlations across 212 independent samples.",
            study_population="Undergraduate and working adult populations",
            sample_size=40000,
            limitations="Primarily correlational designs.",
            rights_note="Scholarly citation under fair dealing.",
        )
        self.research_source_id = self.mgr.insert_source(draft)
        self.evidence_id = self.mgr.add_evidence(
            source_id=self.research_source_id,
            finding="Meta-analytic correlation of r = 0.41 between impulsiveness and procrastination across 24 independent studies.",
            claim="Procrastination correlates strongly with impulsiveness (mean r = 0.41).",
            classification="supporting",
            strength="high",
            limitations="Correlational aggregate.",
        )

    def tearDown(self) -> None:
        import gc
        gc.collect()
        self.temp_dir.cleanup()


class GitaClaimValidationTests(FactCheckerTestCase):
    """Tests covering Bhagavad Gita reference, quotation, and human verification checks."""

    def test_valid_gita_source_reference(self) -> None:
        """Requirement 1: Valid verified source references pass as source_verified."""
        # Verify the verse first
        self.kb.review_verse(
            verse_id=self.gita_verse_id,
            decision="verified",
            reviewer="Prof. M. Hiriyanna",
            evidence="Collated with BORI critical edition Vol. 7, p. 88.",
        )

        claim = Claim(
            claim_id="c_gita_1",
            claim_text="Karma-yoga teaches action without attachment to fruits (Ch 2, V 47).",
            claim_type="gita_paraphrase",
            source_type="gita",
            chapter=2,
            verse=47,
        )
        res = self.checker.validate_claim(claim)
        self.assertTrue(res.source_exists)
        self.assertTrue(res.source_verified)
        self.assertTrue(res.integrity_valid)
        self.assertEqual(res.status, STATUS_PARTIALLY_SUPPORTED)  # Paraphrase requires human assessment
        self.assertIn("paraphrase_requires_human_assessment", res.flags)

    def test_unverified_gita_records(self) -> None:
        """Requirement 3: Unreviewed Gita records are flagged and require human review."""
        # By default, freshly inserted verse is unreviewed
        claim = Claim(
            claim_id="c_gita_unreviewed",
            claim_text="Action without attachment.",
            claim_type="gita_paraphrase",
            source_type="gita",
            chapter=2,
            verse=47,
        )
        res = self.checker.validate_claim(claim)
        self.assertTrue(res.source_exists)
        self.assertFalse(res.source_verified)
        self.assertEqual(res.status, STATUS_REQUIRES_HUMAN_REVIEW)
        self.assertIn("unreviewed_source", res.flags)

    def test_rejected_gita_records(self) -> None:
        """Requirement 3: Explicitly rejected Gita records are flagged as unsupported."""
        self.kb.review_verse(
            verse_id=self.gita_verse_id,
            decision="rejected",
            reviewer="Dr. S. Sharma",
            evidence="Spurious interpolations detected in manuscript witness.",
        )

        claim = Claim(
            claim_id="c_gita_rejected",
            claim_text="Spurious verse claim.",
            claim_type="gita_paraphrase",
            source_type="gita",
            chapter=2,
            verse=47,
        )
        res = self.checker.validate_claim(claim)
        self.assertTrue(res.source_exists)
        self.assertFalse(res.source_verified)
        self.assertEqual(res.status, STATUS_UNSUPPORTED)
        self.assertIn("rejected_source", res.flags)

    def test_tampered_gita_records(self) -> None:
        """Requirement 4: Tampered Gita records fail SHA-256 fingerprint check."""
        self.kb.review_verse(
            verse_id=self.gita_verse_id,
            decision="verified",
            reviewer="Prof. M. Hiriyanna",
            evidence="Collated with BORI critical edition Vol. 7, p. 88.",
        )

        # Tamper directly in SQLite to simulate unauthorized modification
        with self.kb.connection() as conn:
            conn.execute(
                "UPDATE verses SET translation = 'TAMPERED: Inaction is always preferred.' WHERE id = ?;",
                (self.gita_verse_id,),
            )
            conn.commit()

        claim = Claim(
            claim_id="c_gita_tampered",
            claim_text="To action alone hast thou a right.",
            claim_type="gita_quotation",
            source_type="gita",
            chapter=2,
            verse=47,
        )
        res = self.checker.validate_claim(claim)
        self.assertFalse(res.integrity_valid)
        self.assertIn("tampered_record", res.flags)
        self.assertEqual(res.status, STATUS_REQUIRES_HUMAN_REVIEW)

    def test_exact_quotation_matching(self) -> None:
        """Requirement 5: Exact quotation matches against Sanskrit, transliteration, or translation."""
        self.kb.review_verse(
            verse_id=self.gita_verse_id,
            decision="verified",
            reviewer="Prof. M. Hiriyanna",
            evidence="Collated with BORI critical edition Vol. 7, p. 88.",
        )

        # Sanskrit exact quote
        c_sk = Claim(
            claim_id="c_sk_quote",
            claim_text="कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
            claim_type="gita_quotation",
            source_type="gita",
            chapter=2,
            verse=47,
            quote_field="sanskrit",
            quoted_text="कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
            is_direct_quote=True,
        )
        res_sk = self.checker.validate_claim(c_sk)
        self.assertEqual(res_sk.status, STATUS_SOURCE_VERIFIED)
        self.assertTrue(res_sk.quote_matches)

        # Translation exact quote
        c_tr = Claim(
            claim_id="c_tr_quote",
            claim_text="To action alone hast thou a right and never at all to its fruits",
            claim_type="gita_quotation",
            source_type="gita",
            chapter=2,
            verse=47,
            quote_field="translation",
            quoted_text="To action alone hast thou a right and never at all to its fruits",
            is_direct_quote=True,
        )
        res_tr = self.checker.validate_claim(c_tr)
        self.assertEqual(res_tr.status, STATUS_SOURCE_VERIFIED)
        self.assertTrue(res_tr.quote_matches)

    def test_incorrect_quotations(self) -> None:
        """Requirement 6: Fabricated or altered quotations are caught and flagged."""
        self.kb.review_verse(
            verse_id=self.gita_verse_id,
            decision="verified",
            reviewer="Prof. M. Hiriyanna",
            evidence="Collated with BORI critical edition Vol. 7, p. 88.",
        )

        c_fake = Claim(
            claim_id="c_fake_quote",
            claim_text="Fabricated translation: You must never act under any circumstances.",
            claim_type="gita_quotation",
            source_type="gita",
            chapter=2,
            verse=47,
            quote_field="translation",
            quoted_text="You must never act under any circumstances.",
            is_direct_quote=True,
        )
        res = self.checker.validate_claim(c_fake)
        self.assertEqual(res.status, STATUS_UNSUPPORTED)
        self.assertFalse(res.quote_matches)
        self.assertIn("mismatched_quotation", res.flags)


class ResearchClaimValidationTests(FactCheckerTestCase):
    """Tests covering empirical research evidence, approvals, rejections, and contradictions."""

    def test_approved_research_evidence(self) -> None:
        """Requirement 7: Approved research evidence passes verification."""
        # Approve source and evidence
        self.mgr.review_source(
            source_id=self.research_source_id,
            decision="approved",
            reviewer="Dr. Vance",
            notes="Meta-analysis conforms to PRISMA reporting standards.",
        )
        self.mgr.review_evidence(
            evidence_id=self.evidence_id,
            decision="approved",
            reviewer="Dr. Vance",
            notes="Correlation coefficient confirmed from published table 3.",
        )

        claim = Claim(
            claim_id="c_res_approved",
            claim_text="Procrastination correlates strongly with impulsiveness (mean r = 0.41).",
            claim_type="research_finding",
            source_type="research",
            record_id=self.evidence_id,
            quoted_text="Procrastination correlates strongly with impulsiveness (mean r = 0.41).",
            is_direct_quote=True,
        )
        res = self.checker.validate_claim(claim)
        self.assertEqual(res.status, STATUS_SOURCE_VERIFIED)
        self.assertTrue(res.source_verified)

    def test_rejected_research_evidence(self) -> None:
        """Requirement 8: Explicitly rejected research evidence is rejected."""
        self.mgr.review_evidence(
            evidence_id=self.evidence_id,
            decision="rejected",
            reviewer="Dr. Vance",
            notes="Sample duplication error identified in underlying meta-analysis.",
        )

        claim = Claim(
            claim_id="c_res_rejected",
            claim_text="Procrastination correlates strongly with impulsiveness.",
            claim_type="research_finding",
            source_type="research",
            record_id=self.evidence_id,
        )
        res = self.checker.validate_claim(claim)
        self.assertEqual(res.status, STATUS_UNSUPPORTED)
        self.assertIn("rejected_evidence", res.flags)

    def test_unsupported_research_claims(self) -> None:
        """Requirement 9: Nonexistent IDs or fabricated DOIs are flagged as unsupported."""
        c_fake_doi = Claim(
            claim_id="c_fake_doi",
            claim_text="A completely fabricated paper claiming 100% genetic basis.",
            claim_type="research_claim",
            source_type="research",
            doi="10.9999/fabricated.doi.12345",
        )
        res = self.checker.validate_claim(c_fake_doi)
        self.assertEqual(res.status, STATUS_UNSUPPORTED)
        self.assertFalse(res.source_exists)
        self.assertIn("nonexistent_source_reference", res.flags)

    def test_contradicting_evidence_detection(self) -> None:
        """Requirement 10: Explicit conflicting evidence flags claim as contradicted."""
        # Approve primary source
        self.mgr.review_source(
            source_id=self.research_source_id,
            decision="approved",
            reviewer="Dr. Vance",
            notes="Methodology approved.",
        )
        # Add an approved contradicting evidence record
        contra_id = self.mgr.add_evidence(
            source_id=self.research_source_id,
            finding="Perfectionism shows a near-zero correlation with delay discounting (r = 0.02).",
            claim="Perfectionism is the primary driver of task avoidance.",
            classification="contradicting",
            strength="high",
        )
        self.mgr.review_evidence(
            evidence_id=contra_id,
            decision="approved",
            reviewer="Dr. Vance",
            notes="Contradicting finding confirmed by multivariate regression.",
        )

        claim = Claim(
            claim_id="c_contra",
            claim_text="Perfectionism is the primary driver of procrastination.",
            claim_type="research_finding",
            source_type="research",
            source_id=self.research_source_id,
        )
        res = self.checker.validate_claim(claim)
        self.assertEqual(res.status, STATUS_CONTRADICTED)
        self.assertIn("explicit_contradiction_detected", res.flags)
        self.assertIn(contra_id, res.contradicting_evidence_ids)


class SchemaAndBoundaryTests(FactCheckerTestCase):
    """Tests covering missing citations, schema validation, empty collections, and database failures."""

    def test_missing_source_references(self) -> None:
        """Requirement 2 & 11: Missing source references flag missing_citation."""
        claim = Claim(
            claim_id="c_missing_src",
            claim_text="Uncited quotation: Karma is duty performed without desire.",
            claim_type="gita_quotation",
            source_type="none",
        )
        res = self.checker.validate_claim(claim)
        self.assertEqual(res.status, STATUS_UNSUPPORTED)
        self.assertIn("missing_citation", res.flags)

    def test_invalid_input_schemas(self) -> None:
        """Requirement 12: Malformed claims raise ClaimValidationError."""
        # Missing claim_id
        with self.assertRaises(ClaimValidationError):
            Claim.from_dict({"claim_text": "text without id"})

        # Missing claim_text
        with self.assertRaises(ClaimValidationError):
            Claim.from_dict({"claim_id": "c1", "claim_text": "   "})

        # Invalid source_type
        with self.assertRaises(ClaimValidationError):
            Claim.from_dict({"claim_id": "c1", "claim_text": "valid", "source_type": "unknown_provider"})

        # Invalid Gita chapter (> 18)
        with self.assertRaises(ClaimValidationError):
            Claim.from_dict({"claim_id": "c1", "claim_text": "valid", "chapter": 25})

    def test_empty_evidence_collections(self) -> None:
        """Requirement 13: Empty claim batches return clean empty FactCheckReport."""
        report = self.checker.validate_claims([])
        self.assertEqual(report.total_claims, 0)
        self.assertEqual(report.overall_status, "NO_CLAIMS_EVALUATED")
        self.assertTrue(report.human_review_required)

    def test_database_failures(self) -> None:
        """Requirement 14: Inaccessible database handled gracefully without crashing."""
        nonexistent_checker = FactChecker(Path("nonexistent_directory/fake_db.sqlite3"))
        claim = Claim(
            claim_id="c_db_fail",
            claim_text="Any claim text",
            claim_type="gita_quotation",
            source_type="gita",
            chapter=2,
            verse=47,
        )
        res = nonexistent_checker.validate_claim(claim)
        self.assertEqual(res.status, STATUS_UNSUPPORTED)
        self.assertIn("database_unavailable", res.flags)


class IntegrationAndReportTests(FactCheckerTestCase):
    """Tests covering report generation, serialization, and end-to-end integration."""

    def test_validation_report_generation(self) -> None:
        """Requirement 16: Validation report aggregates counts, sources, and serializes to JSON."""
        self.kb.review_verse(
            verse_id=self.gita_verse_id,
            decision="verified",
            reviewer="Prof. M. Hiriyanna",
            evidence="Collated with BORI critical edition Vol. 7, p. 88.",
        )

        claims = [
            Claim(
                claim_id="c_valid_quote",
                claim_text="कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
                claim_type="gita_quotation",
                source_type="gita",
                chapter=2,
                verse=47,
                quoted_text="कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
                quote_field="sanskrit",
                is_direct_quote=True,
            ),
            Claim(
                claim_id="c_missing_ref",
                claim_text="Uncited claim on task delay.",
                claim_type="research_claim",
                source_type="none",
            ),
        ]

        report = self.checker.validate_claims(claims, brief_id="brief_test_101")
        self.assertEqual(report.total_claims, 2)
        self.assertEqual(report.verified_claims, 1)
        self.assertEqual(report.unsupported_claims, 1)
        self.assertEqual(report.overall_status, "FAILED_UNSUPPORTED")
        self.assertIn("c_missing_ref", report.missing_citations)
        self.assertTrue(report.human_review_required)

        # JSON serialization check
        report_json = report.to_json()
        self.assertIn("brief_test_101", report_json)
        self.assertIn("FAILED_UNSUPPORTED", report_json)

    def test_integration_with_orchestrator(self) -> None:
        """Requirement 15: create_brief cleanly integrates with FactChecker claims validation."""
        self.kb.review_verse(
            verse_id=self.gita_verse_id,
            decision="verified",
            reviewer="Prof. M. Hiriyanna",
            evidence="Collated with BORI critical edition Vol. 7, p. 88.",
        )

        test_claim = Claim(
            claim_id="brief_c1",
            claim_text="कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
            claim_type="gita_quotation",
            source_type="gita",
            chapter=2,
            verse=47,
            quoted_text="कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
            quote_field="sanskrit",
            is_direct_quote=True,
        )

        brief = create_brief(
            "What does the Bhagavad Gita teach about action in Chapter 2, Verse 47?",
            kb=self.kb,
            research_mgr=self.mgr,
            claims=[test_claim],
            fact_checker=self.checker,
        )

        self.assertTrue(brief.human_review_required)
        self.assertIn("validation_context", brief.to_dict())
        val_ctx = brief.validation_context
        self.assertEqual(val_ctx.get("total_claims"), 1)
        self.assertEqual(val_ctx.get("verified_claims"), 1)
        self.assertEqual(val_ctx.get("overall_status"), "PASSED_VERIFIED")

    def test_validate_brief_claims_helper(self) -> None:
        """Test validate_brief_claims helper function."""
        brief = create_brief("A test question?", kb=self.kb, research_mgr=self.mgr)
        report = validate_brief_claims(brief, claims=[], fact_checker=self.checker)
        self.assertEqual(report.overall_status, "NO_CLAIMS_EVALUATED")
