"""Unit tests for ANTARĀ Intelligence Engine orchestrator."""

import unittest

from engine.orchestrator import (
    MAX_QUESTION_LENGTH,
    AntaraError,
    QuestionTypeError,
    ValidationError,
    classify_topic,
    create_brief,
    validate_question,
)


class ValidateQuestionTests(unittest.TestCase):
    """Tests for question input validation and normalization."""

    def test_normalizes_whitespace(self):
        self.assertEqual(validate_question("  Why   do people\nwait? "), "Why do people wait?")

    def test_rejects_empty_question(self):
        with self.assertRaises(ValueError):
            validate_question("  ")

    def test_rejects_non_string(self):
        with self.assertRaises(TypeError):
            validate_question(None)

    def test_rejects_question_too_long(self):
        with self.assertRaises(ValueError):
            validate_question("x" * (MAX_QUESTION_LENGTH + 1))

    def test_raises_explicit_validation_error(self):
        """Verify that validation errors raise explicit ValidationError subclasses."""
        with self.assertRaises(ValidationError) as ctx:
            validate_question("   ")
        self.assertIsInstance(ctx.exception, AntaraError)
        self.assertIsInstance(ctx.exception, ValueError)

    def test_raises_explicit_question_type_error(self):
        """Verify that type errors raise explicit QuestionTypeError subclasses."""
        with self.assertRaises(QuestionTypeError) as ctx:
            validate_question(123)  # type: ignore[arg-type]
        self.assertIsInstance(ctx.exception, AntaraError)
        self.assertIsInstance(ctx.exception, TypeError)

    def test_handles_multilingual_utf8_question(self):
        """Verify that Unicode and multilingual strings are preserved and validated."""
        q = "  What does dharma (धर्म) and jñāna (ज्ञान) mean in Sanskrit? "
        self.assertEqual(
            validate_question(q),
            "What does dharma (धर्म) and jñāna (ज्ञान) mean in Sanskrit?",
        )


class ClassificationTests(unittest.TestCase):
    """Tests for topic classification heuristics."""

    def test_classifies_behavior(self):
        self.assertEqual(classify_topic("Why do people procrastinate?"), "human_behavior")

    def test_classifies_philosophy(self):
        self.assertEqual(classify_topic("What does dharma mean?"), "philosophy")

    def test_classifies_technology(self):
        self.assertEqual(classify_topic("How does Python work?"), "technology")

    def test_falls_back_to_general(self):
        self.assertEqual(classify_topic("What is the sky like?"), "general")


class BriefTests(unittest.TestCase):
    """Tests for structured intelligence brief creation."""

    def test_creates_human_supervised_brief(self):
        brief = create_brief("  Why do people procrastinate? ")
        self.assertEqual(brief.question, "Why do people procrastinate?")
        self.assertEqual(brief.topic, "human_behavior")
        self.assertEqual(brief.status, "brief_created")
        self.assertEqual(brief.research_status, "not_started")
        self.assertTrue(brief.human_review_required)
        self.assertGreater(len(brief.objectives), 0)
        self.assertIn("created_at_utc", brief.to_dict())


if __name__ == "__main__":
    unittest.main()

