"""Unit tests for ANTARĀ Module 2: Knowledge Intelligence.

Tests cover schema creation, source normalization, verse insertion, constraints,
cryptographic fingerprinting, controlled JSON import (Unicode, duplicates, dry-run,
partial failure), the human verification workflow (transitions, evidence validation,
tamper detection, automatic invalidation), and audit trails.
"""

from pathlib import Path
import sqlite3
import tempfile
import unittest

from engine.knowledge import (
    DuplicateVerseError,
    ImportValidationError,
    IntegrityVerificationError,
    KnowledgeBase,
    SubstantiveEvidenceError,
    VerseNotFoundError,
    compute_content_hash,
    validate_substantive_evidence,
)


class KnowledgeBaseTestCase(unittest.TestCase):
    """Base test fixture setting up an isolated temporary database for each test."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_knowledge.db"
        self.kb = KnowledgeBase(self.db_path)

    def tearDown(self) -> None:
        import gc
        gc.collect()
        self.temp_dir.cleanup()


class SchemaAndSourceTests(KnowledgeBaseTestCase):
    """Tests for database initialization, foreign keys, and source normalization."""

    def test_initializes_schema_and_enforces_foreign_keys(self) -> None:
        with self.kb.connection() as conn:
            fk_check = conn.execute("PRAGMA foreign_keys;").fetchone()
            self.assertEqual(fk_check[0], 1)

            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
            ).fetchall()
            table_names = [t["name"] for t in tables]
            self.assertIn("sources", table_names)
            self.assertIn("verses", table_names)
            self.assertIn("verification_audit", table_names)

    def test_source_normalization_and_deduplication(self) -> None:
        src_id_1 = self.kb.get_or_create_source(
            title="The Bhagavadgita",
            author="S. Radhakrishnan",
            translator="S. Radhakrishnan",
            edition="1948 Edition",
            year=1948,
        )
        src_id_2 = self.kb.get_or_create_source(
            title="The Bhagavadgita",
            author="S. Radhakrishnan",
            translator="S. Radhakrishnan",
            edition="1948 Edition",
            year=1948,
        )
        # Re-using the same source must return the identical ID
        self.assertEqual(src_id_1, src_id_2)

        # Different edition must create a distinct source ID
        src_id_3 = self.kb.get_or_create_source(
            title="The Bhagavadgita",
            author="S. Radhakrishnan",
            translator="S. Radhakrishnan",
            edition="HarperCollins 1993",
            year=1993,
        )
        self.assertNotEqual(src_id_1, src_id_3)


class VerseValidationAndInsertionTests(KnowledgeBaseTestCase):
    """Tests for verse constraints, duplicate rejection, and initial unreviewed status."""

    def setUp(self) -> None:
        super().setUp()
        self.source_id = self.kb.get_or_create_source(
            title="Critical Edition Test Source",
            author="Scholar A",
        )

    def test_inserts_verse_with_unreviewed_status_and_content_hash(self) -> None:
        v_id = self.kb.insert_verse(
            source_id=self.source_id,
            chapter=2,
            verse=47,
            sanskrit="कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
            transliteration="karmaṇy evādhikāras te mā phaleṣu kadācana |",
            translation="To action alone hast thou a right and never at all to its fruits.",
            language="en",
            locator="Ch 2, Verse 47",
        )
        verse = self.kb.get_verse(v_id)
        self.assertIsNotNone(verse)
        self.assertEqual(verse.chapter, 2)
        self.assertEqual(verse.verse, 47)
        self.assertEqual(verse.verification_status, "unreviewed")
        expected_hash = compute_content_hash(
            2,
            47,
            "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
            "karmaṇy evādhikāras te mā phaleṣu kadācana |",
            "To action alone hast thou a right and never at all to its fruits.",
            "en",
        )
        self.assertEqual(verse.content_hash, expected_hash)
        self.assertEqual(verse.source.title, "Critical Edition Test Source")

    def test_rejects_invalid_chapter_bounds(self) -> None:
        with self.assertRaises(ImportValidationError):
            self.kb.insert_verse(
                source_id=self.source_id,
                chapter=0,
                verse=1,
                sanskrit="ॐ",
                transliteration="Om",
                translation="Om",
            )
        with self.assertRaises(ImportValidationError):
            self.kb.insert_verse(
                source_id=self.source_id,
                chapter=19,
                verse=1,
                sanskrit="ॐ",
                transliteration="Om",
                translation="Om",
            )

    def test_rejects_invalid_verse_number(self) -> None:
        with self.assertRaises(ImportValidationError):
            self.kb.insert_verse(
                source_id=self.source_id,
                chapter=1,
                verse=0,
                sanskrit="ॐ",
                transliteration="Om",
                translation="Om",
            )

    def test_rejects_empty_text_fields(self) -> None:
        with self.assertRaises(ImportValidationError):
            self.kb.insert_verse(
                source_id=self.source_id,
                chapter=1,
                verse=1,
                sanskrit="   ",
                transliteration="dharma",
                translation="duty",
            )

    def test_rejects_duplicate_verse_under_same_source(self) -> None:
        self.kb.insert_verse(
            source_id=self.source_id,
            chapter=2,
            verse=47,
            sanskrit="कर्मण्येवाधिकारस्ते",
            transliteration="karmaṇy evādhikāras te",
            translation="Action alone",
        )
        with self.assertRaises(DuplicateVerseError):
            self.kb.insert_verse(
                source_id=self.source_id,
                chapter=2,
                verse=47,
                sanskrit="कर्मण्येवाधिकारस्ते",
                transliteration="karmaṇy evādhikāras te",
                translation="Action alone (different wording)",
            )

    def test_allows_same_verse_across_multiple_distinct_sources(self) -> None:
        second_source_id = self.kb.get_or_create_source(
            title="Alternative Commentary",
            author="Scholar B",
        )
        v1_id = self.kb.insert_verse(
            source_id=self.source_id,
            chapter=2,
            verse=47,
            sanskrit="कर्मण्येवाधिकारस्ते",
            transliteration="karmaṇy evādhikāras te",
            translation="Translation from Scholar A",
        )
        v2_id = self.kb.insert_verse(
            source_id=second_source_id,
            chapter=2,
            verse=47,
            sanskrit="कर्मण्येवाधिकारस्ते",
            transliteration="karmaṇy evādhikāras te",
            translation="Translation from Scholar B",
        )
        self.assertNotEqual(v1_id, v2_id)
        all_editions = self.kb.get_verses_by_chapter_and_verse(2, 47)
        self.assertEqual(len(all_editions), 2)


class ControlledImporterTests(KnowledgeBaseTestCase):
    """Tests for UTF-8 JSON import: Unicode preservation, dry-runs, duplicate detection, and partial failure."""

    def test_imports_valid_batch_and_preserves_unicode_exactness(self) -> None:
        payload = {
            "source": {
                "title": "Shrimad Bhagavad Gita",
                "author": "Swami Gambhirananda",
                "translator": "Swami Gambhirananda",
                "edition": "Advaita Ashrama 1984",
                "year": 1984,
                "rights_note": "Public research commentary",
            },
            "verses": [
                {
                    "chapter": 2,
                    "verse": 47,
                    "sanskrit": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।\nमा कर्मफलहेतुर्भूर्मा ते सङ्गोऽस्त्वकर्मणि॥",
                    "transliteration": "karmaṇy evādhikāras te mā phaleṣu kadācana |\nmā karma-phala-hetur bhūr mā te saṅgo 'stv akarmaṇi ||",
                    "translation": "Your right is for action alone, not for the fruits. Let not the fruits of action be your motive.",
                    "language": "en",
                    "locator": "p. 104",
                }
            ],
        }
        summary = self.kb.import_json(payload, dry_run=False)
        self.assertEqual(summary.total_rows, 1)
        self.assertEqual(summary.imported, 1)
        self.assertEqual(summary.invalid_rows, 0)
        self.assertEqual(summary.skipped_duplicates, 0)

        verses = self.kb.get_verses_by_chapter_and_verse(2, 47)
        self.assertEqual(len(verses), 1)
        # Exact preservation check:
        self.assertIn("सङ्गोऽस्त्वकर्मणि", verses[0].sanskrit)
        self.assertIn("karmaṇy evādhikāras", verses[0].transliteration)
        self.assertEqual(verses[0].verification_status, "unreviewed")

    def test_dry_run_does_not_commit_records(self) -> None:
        payload = {
            "source": {"title": "Dry Run Test Source", "author": "Test Author"},
            "verses": [
                {
                    "chapter": 1,
                    "verse": 1,
                    "sanskrit": "धर्मक्षेत्रे कुरुक्षेत्रे",
                    "transliteration": "dharma-kṣetre kuru-kṣetre",
                    "translation": "In the holy place of Kurukshetra",
                }
            ],
        }
        summary = self.kb.import_json(payload, dry_run=True)
        self.assertTrue(summary.dry_run)
        self.assertEqual(summary.imported, 1)

        # Database must still have 0 verses
        verses = self.kb.get_verses_by_chapter_and_verse(1, 1)
        self.assertEqual(len(verses), 0)

    def test_handles_duplicates_and_partial_failures_gracefully(self) -> None:
        payload = {
            "source": {"title": "Partial Failure Test", "author": "Test Author"},
            "verses": [
                {  # Row 1: Valid
                    "chapter": 2,
                    "verse": 11,
                    "sanskrit": "अशोच्यानन्वशोचस्त्वम्",
                    "transliteration": "aśocyān anvaśocas tvam",
                    "translation": "You grieve for those who should not be grieved for.",
                },
                {  # Row 2: Invalid chapter (> 18)
                    "chapter": 99,
                    "verse": 1,
                    "sanskrit": "invalid",
                    "transliteration": "invalid",
                    "translation": "invalid",
                },
                {  # Row 3: Missing translation
                    "chapter": 2,
                    "verse": 12,
                    "sanskrit": "न त्वेवाहं जातु नासम्",
                    "transliteration": "na tv evāhaṁ jātu nāsam",
                    "translation": "",
                },
                {  # Row 4: Duplicate of Row 1
                    "chapter": 2,
                    "verse": 11,
                    "sanskrit": "अशोच्यानन्वशोचस्त्वम्",
                    "transliteration": "aśocyān anvaśocas tvam",
                    "translation": "Duplicate translation",
                },
            ],
        }
        summary = self.kb.import_json(payload, dry_run=False)
        self.assertEqual(summary.total_rows, 4)
        self.assertEqual(summary.imported, 1)  # Only row 1 succeeds
        self.assertEqual(summary.invalid_rows, 2)  # Row 2 and row 3 fail
        self.assertEqual(summary.skipped_duplicates, 1)  # Row 4 skipped
        self.assertEqual(len(summary.errors), 2)


class HumanVerificationWorkflowTests(KnowledgeBaseTestCase):
    """Tests for human verification: evidence validation, review transitions, tampering, and invalidation."""

    def setUp(self) -> None:
        super().setUp()
        self.src_id = self.kb.get_or_create_source(
            title="Sanskrit Critical Text",
            author="Bhandarkar Oriental Research Institute (BORI)",
            year=1968,
        )
        self.verse_id = self.kb.insert_verse(
            source_id=self.src_id,
            chapter=2,
            verse=47,
            sanskrit="कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।",
            transliteration="karmaṇy evādhikāras te mā phaleṣu kadācana |",
            translation="Thy right is to work only, but never with its fruits.",
            locator="BORI Critical Ed., Vol. 7, p. 88",
        )

    def test_verifies_verse_with_substantive_evidence(self) -> None:
        audit = self.kb.review_verse(
            verse_id=self.verse_id,
            decision="verified",
            reviewer="Dr. P. Sharma (Sanskrit Philology)",
            evidence="Collated with BORI Critical Edition Vol. 7, Folio 12a, confirmed exact wording.",
            locator="BORI Vol. 7, Folio 12a",
        )
        self.assertEqual(audit.previous_status, "unreviewed")
        self.assertEqual(audit.new_status, "verified")
        self.assertEqual(audit.reviewer, "Dr. P. Sharma (Sanskrit Philology)")

        v = self.kb.get_verse(self.verse_id)
        self.assertEqual(v.verification_status, "verified")
        self.assertEqual(v.locator, "BORI Vol. 7, Folio 12a")

    def test_rejects_insubstantial_evidence_or_url_only(self) -> None:
        # Trivial / short evidence
        with self.assertRaises(SubstantiveEvidenceError):
            self.kb.review_verse(
                verse_id=self.verse_id,
                decision="verified",
                reviewer="Reviewer A",
                evidence="Looks okay to me",
            )

        # URL alone is not substantive evidence
        with self.assertRaises(SubstantiveEvidenceError):
            self.kb.review_verse(
                verse_id=self.verse_id,
                decision="verified",
                reviewer="Reviewer A",
                evidence="https://example.org/bhagavad-gita/ch2-v47",
            )

        # Empty reviewer
        with self.assertRaises(SubstantiveEvidenceError):
            self.kb.review_verse(
                verse_id=self.verse_id,
                decision="verified",
                reviewer="   ",
                evidence="Detailed physical comparison with Gitapress 1971 edition, page 120.",
            )

    def test_review_transitions_and_audit_trail(self) -> None:
        # Transition 1: unreviewed -> verified
        self.kb.review_verse(
            verse_id=self.verse_id,
            decision="verified",
            reviewer="Reviewer 1",
            evidence="Cross-referenced Nirnaya Sagar Press edition 1936, p. 45.",
        )
        # Transition 2: verified -> rejected
        self.kb.review_verse(
            verse_id=self.verse_id,
            decision="rejected",
            reviewer="Reviewer 2",
            evidence="Translation omits key verbal prefix; rejected pending revised wording.",
        )
        # Transition 3: rejected -> unreviewed
        self.kb.review_verse(
            verse_id=self.verse_id,
            decision="unreviewed",
            reviewer="Reviewer 1",
            evidence="Resetting status to unreviewed to await independent third scholar opinion.",
        )

        history = self.kb.get_audit_history(self.verse_id)
        # Including initial SYSTEM:CREATION, there should be 4 audit entries
        self.assertEqual(len(history), 4)
        statuses = [(h.previous_status, h.new_status) for h in history]
        self.assertEqual(
            statuses,
            [
                ("none", "unreviewed"),
                ("unreviewed", "verified"),
                ("verified", "rejected"),
                ("rejected", "unreviewed"),
            ],
        )

    def test_content_modification_automatically_invalidates_prior_verification(self) -> None:
        # First verify the verse
        self.kb.review_verse(
            verse_id=self.verse_id,
            decision="verified",
            reviewer="Reviewer 1",
            evidence="Verified against standard critical text, confirmed accurate.",
        )
        v_before = self.kb.get_verse(self.verse_id)
        self.assertEqual(v_before.verification_status, "verified")

        # Now edit the translation text
        v_after = self.kb.update_verse_content(
            verse_id=self.verse_id,
            sanskrit=v_before.sanskrit,
            transliteration=v_before.transliteration,
            translation="Modified translation text altering philosophical nuance.",
        )
        # Status MUST automatically revert to unreviewed!
        self.assertEqual(v_after.verification_status, "unreviewed")
        self.assertNotEqual(v_before.content_hash, v_after.content_hash)

        # Audit history must record invalidation event
        history = self.kb.get_audit_history(self.verse_id)
        latest_audit = history[-1]
        self.assertEqual(latest_audit.previous_status, "verified")
        self.assertEqual(latest_audit.new_status, "unreviewed")
        self.assertEqual(latest_audit.reviewer, "SYSTEM:CONTENT_MODIFICATION")

    def test_search_and_verified_only_retrieval(self) -> None:
        # Initially verse is unreviewed
        verified_results = self.kb.search_verses(chapter=2, verse=47, verified_only=True)
        self.assertEqual(len(verified_results), 0)

        # Verify verse
        self.kb.review_verse(
            verse_id=self.verse_id,
            decision="verified",
            reviewer="Scholar",
            evidence="Checked against standard Bhandarkar edition; accurate.",
        )
        verified_results = self.kb.search_verses(chapter=2, verse=47, verified_only=True)
        self.assertEqual(len(verified_results), 1)

    def test_tampering_detection_and_verified_only_exclusion(self) -> None:
        # Verify the verse first
        self.kb.review_verse(
            verse_id=self.verse_id,
            decision="verified",
            reviewer="Scholar",
            evidence="Verified with primary manuscript sources; completely accurate.",
        )
        self.assertEqual(len(self.kb.search_verses(verified_only=True)), 1)

        # Simulate out-of-band direct SQL tampering without updating hash
        with self.kb.connection() as conn:
            with conn:
                conn.execute(
                    "UPDATE verses SET translation = 'TAMPERED ILLEGITIMATE TEXT' WHERE id = ?;",
                    (self.verse_id,),
                )

        # Database integrity check must detect the tampering
        report = self.kb.verify_database_integrity()
        self.assertEqual(report["tampered_records"], 1)
        self.assertEqual(report["valid_records"], 0)

        # Verified-only search must automatically reject and exclude the tampered record!
        verified_after_tamper = self.kb.search_verses(verified_only=True)
        self.assertEqual(len(verified_after_tamper), 0)


if __name__ == "__main__":
    unittest.main()
