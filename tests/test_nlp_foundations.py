"""ANTARĀ Intelligence Engine - NLP Foundations Test Suite (Layer 1).

Tests the ten Natural Language Intelligence foundations:
1. Language identification (Telugu, English, Romanized Telugu, mixed).
2. Language metadata propagation through brief and unified response.
3. Intent-detection interfaces and baseline classifier.
4. Query-normalization interfaces with script preservation.
5. Semantic-retrieval abstraction and deterministic mock retriever.
6. Entity and relationship extraction interfaces and baseline extractor.
7. Telugu-English code-switching metadata and ratio metrics.
8. Language-aware provider selection (prioritizing direct Telugu support).
9. NLP provider abstraction (Default and Mock implementations).
10. NLP evaluation interfaces and benchmark metrics.
"""

import unittest

from engine.language import detect_script, detect_language, identify_dialect
from engine.nlp import (
    BaselineEntityExtractor,
    CodeSwitchMetadata,
    DefaultNLPProvider,
    Entity,
    EntityExtractor,
    Intent,
    IntentDetector,
    KeywordIntentDetector,
    LanguageMetadata,
    MockNLPProvider,
    MockSemanticRetriever,
    NLPEvaluationReport,
    NLPEvaluator,
    NLPProvider,
    NormalizedQuery,
    ProviderLanguageCapability,
    QueryNormalizer,
    Relationship,
    SemanticRetriever,
    SemanticSearchResult,
    StandardNLPEvaluator,
    StandardQueryNormalizer,
    detect_code_switching,
    extract_language_metadata,
    select_language_provider,
)
from engine.orchestrator import create_brief
from engine.reasoning import ReasoningAnalysis
from engine.unified_response import build_unified_response


class LanguageIdentificationTests(unittest.TestCase):
    """Tests for script detection, language identification, and Romanized Telugu handling."""

    def test_pure_telugu_language_identification(self):
        text = "కర్మణ్యేవాధికారస్తే మా ఫలేషు కదాచన"
        self.assertEqual(detect_script(text), "telugu")
        self.assertEqual(detect_language(text), "telugu")

    def test_pure_english_language_identification(self):
        text = "How does temporal motivation theory explain procrastination?"
        self.assertEqual(detect_script(text), "latin")
        self.assertEqual(detect_language(text), "english")

    def test_romanized_telugu_is_not_assumed_english(self):
        # Romanized Telugu tokens must NOT be classified as English
        text = "naaku em cheppali?"
        self.assertEqual(detect_script(text), "latin")
        self.assertEqual(detect_language(text), "mixed")
        self.assertEqual(identify_dialect(text), "romanized")

    def test_telugu_english_mixed_code_switched(self):
        text = "భగవద్గీత and modern cognitive science"
        self.assertEqual(detect_script(text), "mixed")
        self.assertEqual(detect_language(text), "mixed")

    def test_extract_language_metadata_helper(self):
        meta: LanguageMetadata = extract_language_metadata("భగవద్గీత and modern cognitive science")
        self.assertEqual(meta.detected_language, "mixed")
        self.assertEqual(meta.response_language, "english")
        self.assertIsNotNone(meta.code_switching)
        self.assertIsInstance(meta.code_switching, CodeSwitchMetadata)
        self.assertIsInstance(meta.to_dict(), dict)

    def test_empty_and_punctuation_script_handling(self):
        self.assertEqual(detect_script(""), "none")
        self.assertEqual(detect_language(""), "unknown")
        self.assertEqual(detect_script("!@#$%^&*() 12345"), "none")
        self.assertEqual(detect_language("!@#$%^&*() 12345"), "unknown")


class CodeSwitchingMetadataTests(unittest.TestCase):
    """Tests for Telugu-English code-switching metrics and ratio calculation."""

    def test_code_switching_detection(self):
        text = "భగవద్గీత teaches self regulation and dharma"
        cs = detect_code_switching(text)
        self.assertTrue(cs.is_code_switched)
        self.assertGreater(cs.telugu_ratio, 0.0)
        self.assertGreater(cs.latin_ratio, 0.0)
        self.assertIsInstance(cs.to_dict(), dict)

    def test_unswitched_english_metadata(self):
        text = "Pure scientific empirical observation"
        cs = detect_code_switching(text)
        self.assertFalse(cs.is_code_switched)
        self.assertEqual(cs.dominant_language, "english")
        self.assertEqual(cs.telugu_ratio, 0.0)
        self.assertEqual(cs.latin_ratio, 1.0)

    def test_unswitched_telugu_metadata(self):
        text = "నిష్కామ కర్మ సిద్ధాంతము"
        cs = detect_code_switching(text)
        self.assertFalse(cs.is_code_switched)
        self.assertEqual(cs.dominant_language, "telugu")
        self.assertEqual(cs.telugu_ratio, 1.0)
        self.assertEqual(cs.latin_ratio, 0.0)


class IntentDetectionInterfaceTests(unittest.TestCase):
    """Tests for IntentDetector contract and KeywordIntentDetector baseline."""

    def setUp(self):
        self.detector: IntentDetector = KeywordIntentDetector()

    def test_detects_philosophical_intent(self):
        intent = self.detector.detect_intent("What is the core teaching of Gita on karma?")
        self.assertEqual(intent.name, "philosophical_query")
        self.assertEqual(intent.domain, "traditional_knowledge")
        self.assertGreaterEqual(intent.confidence, 0.8)

    def test_detects_scientific_intent(self):
        intent = self.detector.detect_intent("What does psychological research say on delay discounting?")
        self.assertEqual(intent.name, "scientific_query")
        self.assertEqual(intent.domain, "empirical_research")

    def test_detects_comparative_intent(self):
        intent = self.detector.detect_intent("Compare Gita on karma with modern neuroscience of dopamine.")
        self.assertEqual(intent.name, "comparative_inquiry")
        self.assertEqual(intent.domain, "cross_disciplinary")

    def test_detects_live_information_intent(self):
        intent = self.detector.detect_intent("What are the latest 2026 updates on cognitive research?")
        self.assertEqual(intent.name, "current_information")
        self.assertEqual(intent.domain, "live_web")


class QueryNormalizationInterfaceTests(unittest.TestCase):
    """Tests for QueryNormalizer contract and script-preserving normalization."""

    def setUp(self):
        self.normalizer: QueryNormalizer = StandardQueryNormalizer()

    def test_preserves_telugu_unicode_without_destructive_transforms(self):
        raw = "  నిష్కామ   కర్మ   అనగా నేమి?  \n"
        norm = self.normalizer.normalize(raw)
        self.assertIsInstance(norm, NormalizedQuery)
        self.assertEqual(norm.normalized, "నిష్కామ కర్మ అనగా నేమి?")
        self.assertEqual(norm.script, "telugu")
        self.assertEqual(norm.language, "telugu")
        self.assertFalse(norm.case_folded)
        self.assertIn("కర్మ", norm.tokens)

    def test_normalizes_whitespace_in_english(self):
        raw = "   Explain   delay   discounting\tstudies?  "
        norm = self.normalizer.normalize(raw)
        self.assertEqual(norm.normalized, "Explain delay discounting studies?")
        self.assertEqual(norm.script, "latin")
        self.assertEqual(norm.language, "english")


class SemanticRetrievalInterfaceTests(unittest.TestCase):
    """Tests for SemanticRetriever contract and MockSemanticRetriever."""

    def setUp(self):
        self.retriever: SemanticRetriever = MockSemanticRetriever([
            SemanticSearchResult(
                record_id="bg_2_47",
                text="karmaṇy evādhikāras te mā phaleṣu kadācana",
                score=0.95,
                source="gita",
            ),
            SemanticSearchResult(
                record_id="steel_2007",
                text="Temporal motivation theory and procrastination",
                score=0.82,
                source="research",
            ),
            SemanticSearchResult(
                record_id="low_score",
                text="Irrelevant context",
                score=0.20,
                source="web",
            ),
        ])

    def test_retrieves_candidates_above_threshold(self):
        results = self.retriever.retrieve_semantic("nishkama karma", top_k=2, threshold=0.5)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].record_id, "bg_2_47")
        self.assertEqual(results[1].record_id, "steel_2007")

    def test_threshold_filters_low_confidence(self):
        results = self.retriever.retrieve_semantic("query", top_k=5, threshold=0.9)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].record_id, "bg_2_47")


class EntityAndRelationshipExtractionTests(unittest.TestCase):
    """Tests for EntityExtractor contract and BaselineEntityExtractor."""

    def setUp(self):
        self.extractor: EntityExtractor = BaselineEntityExtractor()

    def test_extracts_known_entities(self):
        text = "Krishna advises Arjuna on Nishkama Karma in the Bhagavad Gita."
        entities = self.extractor.extract_entities(text)
        types = {e.entity_type for e in entities}
        self.assertIn("person", types)
        self.assertIn("concept", types)
        self.assertIn("source", types)
        self.assertIsInstance(entities[0], Entity)

    def test_extracts_relationships(self):
        text = "Krishna instructs Arjuna regarding Nishkama Karma."
        entities = self.extractor.extract_entities(text)
        relations = self.extractor.extract_relationships(text, entities)
        self.assertTrue(any(r.source_entity == "Krishna" and r.target_entity == "Arjuna" for r in relations))
        self.assertIsInstance(relations[0], Relationship)


class LanguageAwareProviderSelectionTests(unittest.TestCase):
    """Tests for language-aware provider routing preserving direct Telugu reasoning."""

    def setUp(self):
        self.providers = [
            ProviderLanguageCapability(
                provider_name="ollama_local",
                supported_languages=["telugu", "english"],
                supports_direct_telugu=True,
                requires_translation=False,
            ),
            ProviderLanguageCapability(
                provider_name="cloud_english_only",
                supported_languages=["english"],
                supports_direct_telugu=False,
                requires_translation=True,
            ),
        ]

    def test_selects_direct_telugu_provider_without_forced_translation(self):
        chosen = select_language_provider(self.providers, "telugu")
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.provider_name, "ollama_local")
        self.assertTrue(chosen.supports_direct_telugu)
        self.assertFalse(chosen.requires_translation)

    def test_selects_english_provider(self):
        chosen = select_language_provider(self.providers, "english")
        self.assertIsNotNone(chosen)
        self.assertIn("english", chosen.supported_languages)


class NLPProviderAbstractionTests(unittest.TestCase):
    """Tests for the unified NLPProvider interface and implementations."""

    def test_default_nlp_provider(self):
        provider: NLPProvider = DefaultNLPProvider()
        lang = provider.identify_language("నిష్కామ కర్మ")
        self.assertEqual(lang, "telugu")

        norm = provider.normalize_query("  Why do people wait?  ")
        self.assertEqual(norm.normalized, "Why do people wait?")

        intent = provider.detect_intent("What does Bhagavad Gita teach?")
        self.assertEqual(intent.name, "philosophical_query")

    def test_mock_nlp_provider(self):
        custom_intent = Intent(intent_id="custom_1", name="custom_intent", confidence=1.0)
        mock_p = MockNLPProvider(language="telugu", intent=custom_intent)
        self.assertEqual(mock_p.identify_language("any text"), "telugu")
        self.assertEqual(mock_p.detect_intent("any text").name, "custom_intent")


class NLPEvaluationInterfaceTests(unittest.TestCase):
    """Tests for NLPEvaluator contract and benchmark execution."""

    def test_standard_evaluator_measures_accuracy_and_latency(self):
        evaluator: NLPEvaluator = StandardNLPEvaluator()
        test_cases = [
            {"text": "నిష్కామ కర్మ", "expected_language": "telugu", "expected_intent": "philosophical_query"},
            {"text": "Psychological study of dopamine", "expected_language": "english", "expected_intent": "scientific_query"},
            {"text": "naaku em cheppali?", "expected_language": "mixed"},
        ]
        report: NLPEvaluationReport = evaluator.evaluate(test_cases)
        self.assertEqual(report.sample_count, 3)
        self.assertGreaterEqual(report.accuracy, 0.8)
        self.assertTrue(report.passed)
        self.assertGreaterEqual(report.latency_ms, 0.0)


class OrchestrationNLPPropagationTests(unittest.TestCase):
    """Tests ensuring NLP metadata propagates into IntelligenceBrief and UnifiedResponse."""

    def test_create_brief_propagates_nlp_metadata(self):
        brief = create_brief("నిష్కామ కర్మ సిద్ధాంతము వివరించండి")
        self.assertEqual(brief.query_language, "telugu")
        self.assertEqual(brief.response_language, "telugu")
        self.assertIsNotNone(brief.code_switching)
        self.assertEqual(brief.code_switching.get("dominant_language"), "telugu")

    def test_unified_response_surfaces_language_metadata(self):
        brief = create_brief("Explain nishkama karma.")
        mock_analysis = ReasoningAnalysis(
            report_id="test_nlp_report_01",
            question=brief.question,
            executive_summary="Summary.",
            philosophical_perspective="Gita perspective.",
            relevant_gita_teachings=[],
            modern_scientific_perspectives="Scientific perspective.",
            supporting_research_evidence=[],
            contradicting_research_evidence=[],
            philosophical_and_scientific_similarities=[],
            important_differences=[],
            critical_analysis="Critical analysis.",
            original_synthesized_insight="Novel insight.",
            practical_implications=["Guidance 1"],
            limitations_and_uncertainty=["Limitation 1"],
            research_gaps=["Gap 1"],
            exact_source_citations=[],
            claims_requiring_human_review=[],
            status="pending_review",
            human_review_required=True,
            created_at_utc="2026-11-08T12:00:00Z",
            updated_at_utc="2026-11-08T12:00:00Z",
        )
        unified = build_unified_response(brief, mock_analysis)
        self.assertIn("language_metadata", unified.to_dict())
        meta = unified.language_metadata
        self.assertIn("query_language", meta)
        self.assertIn("response_language", meta)
        self.assertIn("code_switching", meta)


if __name__ == "__main__":
    unittest.main()
