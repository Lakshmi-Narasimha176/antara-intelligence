"""Unit tests for ANTARĀ Module 1 & Module 2 Knowledge Retrieval Bridge.

Tests cover:
- Verified verse retrieval
- Exclusion of unreviewed records
- Exclusion of rejected records
- Exclusion of modified or integrity-invalidated records
- Defense-in-depth against direct SQL tampering
- Source provenance preservation
- Empty search results handling
- Irrelevant / non-philosophical query handling
- Missing database and failure resilience
- Integration with Intelligence Orchestrator (create_brief)
- Backward compatibility with Module 1 baseline
"""

import json
from pathlib import Path
import tempfile
import unittest

from engine.knowledge import KnowledgeBase
from engine.orchestrator import create_brief
from engine.retrieval import (
    extract_search_keywords,
    extract_verse_references,
    retrieve_knowledge,
    should_retrieve_knowledge,
)


class RetrievalBridgeTestCase(unittest.TestCase):
    """Base test fixture setting up an isolated temporary KnowledgeBase."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_retrieval.db"
        self.kb = KnowledgeBase(self.db_path)

        # Seed an authentic test source and verse
        self.source_id = self.kb.get_or_create_source(
            title="The Bhagavadgita: With Text, Translation and Notes",
            author="Dr. S. Radhakrishnan",
            translator="Dr. S. Radhakrishnan",
            edition="HarperCollins 1993",
            year=1993,
            url="https://archive.org/details/the-bhagavadgita-radhakrishnan",
            rights_note="Public research commentary under scholarly fair dealing.",
        )
        self.verse_id = self.kb.insert_verse(
            source_id=self.source_id,
            chapter=2,
            verse=47,
            sanskrit="कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।\nमा कर्मफलहेतुर्भूर्मा ते सङ्गोऽस्त्वकर्मणि॥",
            transliteration="karmaṇy evādhikāras te mā phaleṣu kadācana |\nmā karma-phala-hetur bhūr mā te saṅgo 'stv akarmaṇi ||",
            translation="To action alone hast thou a right and never at all to its fruits; let not the fruits of action be thy motive; neither let there be in thee any attachment to inaction.",
            language="en",
            locator="Chapter 2, Verse 47, p. 119",
            notes="Foundational formulation of Niṣkāma Karma (action without desire for fruits).",
        )

    def tearDown(self) -> None:
        import gc
        gc.collect()
        self.temp_dir.cleanup()


class VerifiedRetrievalTests(RetrievalBridgeTestCase):
    """Tests for verified verse retrieval and provenance preservation."""

    def test_retrieves_verified_verse_by_chapter_and_verse(self) -> None:
        # Review and verify the verse
        self.kb.review_verse(
            verse_id=self.verse_id,
            decision="verified",
            reviewer="Dr. S. Sharma (Sanskrit Philology)",
            evidence="Collated with Bhandarkar Oriental Research Institute (BORI) Critical Edition Vol 7, p. 88.",
            locator="BORI Vol. 7, p. 88; Radhakrishnan p. 119",
        )

        question = "What does the Bhagavad Gita teach in Chapter 2, Verse 47 about action?"
        result = retrieve_knowledge(question, kb=self.kb)

        self.assertTrue(result.retrieval_indicated)
        self.assertEqual(result.status, "retrieved_verified")
        self.assertEqual(result.total_found, 1)
        self.assertEqual(len(result.records), 1)

        record = result.records[0]
        self.assertEqual(record.chapter, 2)
        self.assertEqual(record.verse, 47)
        self.assertIn("कर्मण्येवाधिकारस्ते", record.sanskrit)
        self.assertIn("karmaṇy evādhikāras", record.transliteration)
        self.assertIn("action alone hast thou a right", record.translation)
        self.assertEqual(record.evidence_type, "verified_primary_source")

        # Source provenance preservation
        self.assertEqual(record.source["title"], "The Bhagavadgita: With Text, Translation and Notes")
        self.assertEqual(record.source["author"], "Dr. S. Radhakrishnan")
        self.assertEqual(record.source["year"], 1993)
        self.assertEqual(record.locator, "BORI Vol. 7, p. 88; Radhakrishnan p. 119")

    def test_retrieves_verified_verse_by_keyword_search(self) -> None:
        self.kb.review_verse(
            verse_id=self.verse_id,
            decision="verified",
            reviewer="Dr. S. Sharma",
            evidence="Checked against published Sanskrit text and verified accurate.",
        )

        # Question without explicit chapter/verse number, but with keyword 'action' and 'fruits'
        question = "What is the philosophical teaching on action and fruits in the Gita?"
        result = retrieve_knowledge(question, kb=self.kb)

        self.assertEqual(result.status, "retrieved_verified")
        self.assertGreaterEqual(result.total_found, 1)
        self.assertEqual(result.records[0].chapter, 2)
        self.assertEqual(result.records[0].verse, 47)


class UnverifiedExclusionTests(RetrievalBridgeTestCase):
    """Tests guaranteeing that unverified, rejected, or invalidated records are never retrieved."""

    def test_excludes_unreviewed_records(self) -> None:
        # Verse is newly inserted, status is 'unreviewed'
        question = "What does Chapter 2, Verse 47 say?"
        result = retrieve_knowledge(question, kb=self.kb)

        self.assertTrue(result.retrieval_indicated)
        self.assertEqual(result.status, "no_verified_knowledge_found")
        self.assertEqual(result.total_found, 0)
        self.assertEqual(len(result.records), 0)

    def test_excludes_rejected_records(self) -> None:
        self.kb.review_verse(
            verse_id=self.verse_id,
            decision="rejected",
            reviewer="Scholar",
            evidence="Translation defective; rejected pending scholarly revision.",
        )

        question = "What does Chapter 2, Verse 47 say?"
        result = retrieve_knowledge(question, kb=self.kb)

        self.assertEqual(result.status, "no_verified_knowledge_found")
        self.assertEqual(result.total_found, 0)

    def test_excludes_modified_and_invalidated_records(self) -> None:
        # First verify
        self.kb.review_verse(
            verse_id=self.verse_id,
            decision="verified",
            reviewer="Scholar",
            evidence="Verified against primary printed edition.",
        )
        # Modify content (automatically invalidates verification)
        self.kb.update_verse_content(
            verse_id=self.verse_id,
            sanskrit="कर्मण्येवाधिकारस्ते",
            transliteration="karmaṇy evādhikāras te",
            translation="Altered translation text.",
        )

        question = "What does Chapter 2, Verse 47 say?"
        result = retrieve_knowledge(question, kb=self.kb)
        self.assertEqual(result.status, "no_verified_knowledge_found")
        self.assertEqual(result.total_found, 0)

    def test_excludes_tampered_records_via_defense_in_depth(self) -> None:
        # Verify the verse first
        self.kb.review_verse(
            verse_id=self.verse_id,
            decision="verified",
            reviewer="Scholar",
            evidence="Collated with primary critical text.",
        )

        # Simulate direct SQL tampering without updating hash
        with self.kb.connection() as conn:
            with conn:
                conn.execute(
                    "UPDATE verses SET translation = 'MALICIOUS TAMPERED TRANSLATION' WHERE id = ?;",
                    (self.verse_id,),
                )

        question = "What does Chapter 2, Verse 47 teach?"
        result = retrieve_knowledge(question, kb=self.kb)
        self.assertEqual(result.status, "no_verified_knowledge_found")
        self.assertEqual(result.total_found, 0)


class QueryRoutingAndFallbackTests(RetrievalBridgeTestCase):
    """Tests for question classification, non-philosophical queries, empty searches, and DB failures."""

    def test_bypasses_retrieval_for_non_philosophical_questions(self) -> None:
        questions = [
            ("Why do people procrastinate even when they know what matters?", "human_behavior"),
            ("How does Python asyncio work under the hood?", "technology"),
            ("How can I organize my calendar for deep work?", "productivity"),
        ]
        for q, topic in questions:
            self.assertFalse(should_retrieve_knowledge(q, topic=topic))
            result = retrieve_knowledge(q, topic=topic, kb=self.kb)
            self.assertFalse(result.retrieval_indicated)
            self.assertEqual(result.status, "retrieval_not_indicated")
            self.assertEqual(result.total_found, 0)
            self.assertEqual(result.records, [])

    def test_triggers_retrieval_for_philosophical_and_gita_questions(self) -> None:
        queries = [
            ("What does dharma mean in Indian philosophy?", "philosophy"),
            ("Explain the concept of karma-yoga in Bhagavad Gita", "philosophy"),
            ("What does BG 2.47 teach?", "general"),
            ("How does the Gita address fear and attachment?", "human_behavior"),
        ]
        for q, topic in queries:
            self.assertTrue(
                should_retrieve_knowledge(q, topic=topic),
                f"Expected should_retrieve_knowledge to be True for: {q}",
            )

    def test_extract_verse_references_patterns(self) -> None:
        cases = [
            ("What is taught in Chapter 2, Verse 47?", [(2, 47)]),
            ("Explain Ch 18 v 66 in the Gita", [(18, 66)]),
            ("Consider 2.47 and 3.19 together", [(2, 47), (3, 19)]),
            ("What about BG 2:47?", [(2, 47)]),
            ("Random question with chapter 99 verse 999", []),  # Invalid chapter
        ]
        for text, expected in cases:
            self.assertEqual(extract_verse_references(text), expected)

    def test_extract_search_keywords_filters_stopwords(self) -> None:
        q = "What does dharma and karma mean in the Bhagavad Gita?"
        kw = extract_search_keywords(q)
        self.assertIn("dharma", kw)
        self.assertIn("karma", kw)
        self.assertIn("bhagavad", kw)
        self.assertIn("gita", kw)
        self.assertNotIn("what", kw)
        self.assertNotIn("does", kw)
        self.assertNotIn("and", kw)
        self.assertNotIn("in", kw)
        self.assertNotIn("the", kw)

    def test_returns_empty_result_when_no_records_match(self) -> None:
        self.kb.review_verse(
            verse_id=self.verse_id,
            decision="verified",
            reviewer="Scholar",
            evidence="Verified against primary printed critical edition text; confirmed accurate.",
        )
        # Search for a verse not in the database (e.g. Chapter 18, Verse 66)
        question = "What does Chapter 18, Verse 66 say about surrender?"
        result = retrieve_knowledge(question, kb=self.kb)
        self.assertTrue(result.retrieval_indicated)
        self.assertEqual(result.status, "no_verified_knowledge_found")
        self.assertEqual(result.total_found, 0)
        self.assertIn("No verified primary source records match", result.reason)

    def test_handles_missing_database_safely(self) -> None:
        non_existent = Path(self.temp_dir.name) / "does_not_exist.db"
        result = retrieve_knowledge(
            "What does the Gita say about dharma?",
            topic="philosophy",
            db_path=non_existent,
        )
        self.assertTrue(result.retrieval_indicated)
        self.assertEqual(result.status, "database_unavailable")
        self.assertEqual(result.total_found, 0)
        self.assertEqual(result.records, [])


class OrchestratorIntegrationTests(RetrievalBridgeTestCase):
    """Tests for integration with create_brief and backward compatibility."""

    def test_create_brief_attaches_verified_knowledge(self) -> None:
        self.kb.review_verse(
            verse_id=self.verse_id,
            decision="verified",
            reviewer="Dr. S. Sharma",
            evidence="Collated against critical edition.",
        )

        question = "What does Bhagavad Gita Chapter 2, Verse 47 teach on duty?"
        brief = create_brief(question, kb=self.kb)

        self.assertEqual(brief.topic, "philosophy")
        self.assertEqual(brief.status, "brief_created")
        self.assertTrue(brief.human_review_required)
        self.assertIn("knowledge_context", brief.to_dict())

        ctx = brief.knowledge_context
        self.assertEqual(ctx["status"], "retrieved_verified")
        self.assertEqual(ctx["total_found"], 1)
        self.assertEqual(len(ctx["records"]), 1)
        self.assertEqual(ctx["records"][0]["chapter"], 2)
        self.assertEqual(ctx["records"][0]["verse"], 47)

        # Ensure JSON serializable
        serialized = json.dumps(brief.to_dict())
        self.assertIsInstance(serialized, str)

    def test_backward_compatibility_with_standard_brief_creation(self) -> None:
        # Standard Module 1 baseline call with no extra parameters
        brief = create_brief("Why do people procrastinate even when they know what matters?")

        self.assertEqual(brief.question, "Why do people procrastinate even when they know what matters?")
        self.assertEqual(brief.topic, "human_behavior")
        self.assertEqual(brief.status, "brief_created")
        self.assertEqual(brief.research_status, "not_started")
        self.assertTrue(brief.human_review_required)
        self.assertGreater(len(brief.objectives), 0)
        self.assertIn("created_at_utc", brief.to_dict())
        self.assertIn("knowledge_context", brief.to_dict())

        # For non-philosophical query, retrieval is not indicated
        self.assertFalse(brief.knowledge_context["retrieval_indicated"])
        self.assertEqual(brief.knowledge_context["status"], "retrieval_not_indicated")
        self.assertEqual(brief.knowledge_context["total_found"], 0)


if __name__ == "__main__":
    unittest.main()
