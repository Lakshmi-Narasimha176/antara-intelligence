"""ANTARĀ Intelligence Engine - Natural Language Intelligence Foundations (Layer 1).

Establishes foundational interfaces, data contracts, and baseline implementations for:
1. Language identification (Telugu, English, Romanized Telugu, mixed).
2. Language metadata propagation.
3. Intent-detection interfaces.
4. Query-normalization interfaces.
5. Semantic-retrieval interfaces.
6. Entity and relationship extraction interfaces.
7. Telugu-English code-switching metadata.
8. Language-aware provider selection.
9. NLP provider abstraction.
10. NLP evaluation interfaces.

Telugu is ANTARĀ's foundational language, with Telugu and English as equal primary
working languages. Deep neural NLU, morphology, and tokenizers belong to Layer 2.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
import logging
import re
from typing import Any

from engine.language import (
    TELUGU_SCRIPT_RE,
    LATIN_SCRIPT_RE,
    detect_script,
    detect_language,
    identify_dialect,
)

logger = logging.getLogger("antara.nlp")


# ---------------------------------------------------------------------------
# 1 & 7. Code-Switching & Language Metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CodeSwitchMetadata:
    """Metadata describing Telugu-English code-switching and multilingual mixing."""

    is_code_switched: bool
    dominant_language: str
    secondary_language: str | None = None
    telugu_ratio: float = 0.0
    latin_ratio: float = 0.0
    switch_points: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary."""
        return asdict(self)


def detect_code_switching(text: str) -> CodeSwitchMetadata:
    """Analyze text for Telugu-English code-switching and script distribution.

    Args:
        text: Input string in Telugu, English, mixed script, or Romanized Telugu.

    Returns:
        CodeSwitchMetadata with calculated token ratios and switch boundaries.
    """
    if not text or not text.strip():
        return CodeSwitchMetadata(
            is_code_switched=False,
            dominant_language="unknown",
            secondary_language=None,
            telugu_ratio=0.0,
            latin_ratio=0.0,
            switch_points=[],
        )

    tokens = text.strip().split()
    if not tokens:
        return CodeSwitchMetadata(
            is_code_switched=False,
            dominant_language="unknown",
            secondary_language=None,
            telugu_ratio=0.0,
            latin_ratio=0.0,
            switch_points=[],
        )

    telugu_count = 0
    latin_count = 0
    token_scripts: list[tuple[str, str]] = []

    for tok in tokens:
        has_tel = bool(TELUGU_SCRIPT_RE.search(tok))
        has_lat = bool(LATIN_SCRIPT_RE.search(tok))
        if has_tel and has_lat:
            s = "mixed"
            telugu_count += 1
            latin_count += 1
        elif has_tel:
            s = "telugu"
            telugu_count += 1
        elif has_lat:
            s = "latin"
            latin_count += 1
        else:
            s = "other"
        token_scripts.append((tok, s))

    total = max(1, telugu_count + latin_count)
    t_ratio = round(telugu_count / total, 3)
    l_ratio = round(latin_count / total, 3)

    # Detect switch points where token script changes between telugu and latin
    switch_points: list[str] = []
    prev_script: str | None = None
    for tok, s in token_scripts:
        if s in ("telugu", "latin"):
            if prev_script and s != prev_script:
                switch_points.append(tok)
            prev_script = s

    is_switched = (telugu_count > 0 and latin_count > 0) or bool(switch_points)

    if telugu_count > latin_count:
        dom = "telugu"
        sec = "english" if latin_count > 0 else None
    elif latin_count > telugu_count:
        dom = "english"
        sec = "telugu" if telugu_count > 0 else None
    else:
        dom = "mixed"
        sec = "mixed" if is_switched else None

    # Check for Romanized Telugu when script is purely Latin
    if dom == "english" and identify_dialect(text) == "romanized":
        dom = "mixed"
        sec = "telugu"
        is_switched = True

    return CodeSwitchMetadata(
        is_code_switched=is_switched,
        dominant_language=dom,
        secondary_language=sec,
        telugu_ratio=t_ratio,
        latin_ratio=l_ratio,
        switch_points=switch_points,
    )


# ---------------------------------------------------------------------------
# 2. Comprehensive Language Metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LanguageMetadata:
    """Comprehensive language metadata bundle propagated through Layer 1."""

    query_text: str
    detected_script: str
    detected_language: str
    response_language: str
    dialect: str | None = None
    code_switching: CodeSwitchMetadata | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary."""
        d = asdict(self)
        if self.code_switching:
            d["code_switching"] = self.code_switching.to_dict()
        return d


def extract_language_metadata(
    text: str,
    target_response_language: str | None = None,
) -> LanguageMetadata:
    """Build full LanguageMetadata for an input string.

    Args:
        text: User query or prompt.
        target_response_language: Optional preferred language override.

    Returns:
        Populated LanguageMetadata instance.
    """
    script = detect_script(text)
    lang = detect_language(text)
    dialect = identify_dialect(text)
    cs = detect_code_switching(text)

    # If target not specified, preserve user language: Telugu stays Telugu
    if target_response_language:
        resp_lang = target_response_language
    elif lang == "telugu":
        resp_lang = "telugu"
    else:
        resp_lang = "english"

    return LanguageMetadata(
        query_text=text,
        detected_script=script,
        detected_language=lang,
        response_language=resp_lang,
        dialect=dialect,
        code_switching=cs,
    )


# ---------------------------------------------------------------------------
# 3. Intent-Detection Interfaces
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Intent:
    """Structured representation of identified user intent."""

    intent_id: str
    name: str
    confidence: float = 1.0
    domain: str = "general"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IntentDetector(ABC):
    """Abstract interface for detecting intent from queries."""

    @abstractmethod
    def detect_intent(self, text: str, context: dict[str, Any] | None = None) -> Intent:
        """Analyze text and return classified intent."""
        pass


class KeywordIntentDetector(IntentDetector):
    """Deterministic Layer 1 baseline intent detector using domain vocabulary."""

    PHILOSOPHICAL_KEYWORDS = frozenset({
        "dharma", "karma", "gita", "gītā", "moksha", "atman", "brahman",
        "krishna", "arjuna", "yoga", "vedanta", "upanishad", "samkhya",
        "ధర్మ", "కర్మ", "గీత", "మోక్ష", "ఆత్మ", "బ్రహ్మ",
    })

    RESEARCH_KEYWORDS = frozenset({
        "study", "research", "science", "psychology", "empirical", "experiment",
        "dopamine", "cognitive", "meta-analysis", "clinical", "sample size",
    })

    LIVE_KEYWORDS = frozenset({
        "current", "latest", "recent", "today", "now", "2024", "2025", "2026",
        "news", "update", "updates", "breakthrough", "policy",
    })

    def detect_intent(self, text: str, context: dict[str, Any] | None = None) -> Intent:
        """Classify user intent into philosophical, scientific, factual, or general."""
        lower = text.lower()
        has_philo = any(k in lower for k in self.PHILOSOPHICAL_KEYWORDS)
        has_sci = any(k in lower for k in self.RESEARCH_KEYWORDS)
        has_live = any(k in lower for k in self.LIVE_KEYWORDS)

        # If query specifically asks for latest / current / live information
        if has_live:
            return Intent(
                intent_id="intent_current_information",
                name="current_information",
                confidence=0.9,
                domain="live_web",
                metadata={"subsystem": "live_internet"},
            )

        if has_philo and has_sci:
            return Intent(
                intent_id="intent_comparative_inquiry",
                name="comparative_inquiry",
                confidence=0.95,
                domain="cross_disciplinary",
                metadata={"traditional": True, "scientific": True},
            )
        if has_philo:
            return Intent(
                intent_id="intent_philosophical_query",
                name="philosophical_query",
                confidence=0.9,
                domain="traditional_knowledge",
                metadata={"subsystem": "gita"},
            )
        if has_sci:
            return Intent(
                intent_id="intent_scientific_query",
                name="scientific_query",
                confidence=0.9,
                domain="empirical_research",
                metadata={"subsystem": "research"},
            )

        return Intent(
            intent_id="intent_general_inquiry",
            name="general_inquiry",
            confidence=0.7,
            domain="general",
        )


# ---------------------------------------------------------------------------
# 4. Query-Normalization Interfaces
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NormalizedQuery:
    """Normalized query structure with script preservation."""

    original: str
    normalized: str
    script: str
    language: str
    tokens: list[str]
    case_folded: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class QueryNormalizer(ABC):
    """Abstract interface for query normalization."""

    @abstractmethod
    def normalize(self, query: str) -> NormalizedQuery:
        """Normalize query string without corrupting Unicode or non-Latin scripts."""
        pass


class StandardQueryNormalizer(QueryNormalizer):
    """Deterministic Layer 1 normalizer preserving Telugu Unicode and formatting Latin."""

    def normalize(self, query: str) -> NormalizedQuery:
        cleaned = re.sub(r"[\r\n\t]+", " ", query).strip()
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        script = detect_script(cleaned)
        lang = detect_language(cleaned)

        # Do not case-fold pure Telugu script (no uppercase in Telugu)
        if script == "telugu":
            norm = cleaned
            folded = False
        else:
            norm = cleaned
            folded = False

        tokens = norm.split()
        return NormalizedQuery(
            original=query,
            normalized=norm,
            script=script,
            language=lang,
            tokens=tokens,
            case_folded=folded,
        )


# ---------------------------------------------------------------------------
# 5. Semantic-Retrieval Interfaces
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SemanticSearchResult:
    """Standard contract for semantic retrieval candidates."""

    record_id: str | int
    text: str
    score: float
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SemanticRetriever(ABC):
    """Abstract interface for dense/semantic retrieval providers."""

    @abstractmethod
    def retrieve_semantic(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> list[SemanticSearchResult]:
        """Perform semantic retrieval for query."""
        pass


class MockSemanticRetriever(SemanticRetriever):
    """Deterministic mock semantic retriever for offline Layer 1 testing."""

    def __init__(self, fixtures: list[SemanticSearchResult] | None = None) -> None:
        self.fixtures = fixtures or [
            SemanticSearchResult(
                record_id="bg_2_47",
                text="karmaṇy evādhikāras te mā phaleṣu kadācana",
                score=0.94,
                source="bhagavad_gita",
                metadata={"chapter": 2, "verse": 47},
            )
        ]

    def retrieve_semantic(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> list[SemanticSearchResult]:
        results = [r for r in self.fixtures if r.score >= threshold]
        return results[:top_k]


# ---------------------------------------------------------------------------
# 6. Entity and Relationship Extraction Interfaces
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Entity:
    """Named or conceptual entity identified in text."""

    text: str
    entity_type: str  # e.g., 'concept', 'person', 'source', 'deity', 'neuro_chemical'
    start_char: int | None = None
    end_char: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Relationship:
    """Semantic relation between two entities."""

    source_entity: str
    relation_type: str  # e.g., 'teaches', 'correlates_with', 'opposes', 'part_of'
    target_entity: str
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EntityExtractor(ABC):
    """Abstract contract for entity and relationship extraction."""

    @abstractmethod
    def extract_entities(self, text: str) -> list[Entity]:
        """Extract domain entities from text."""
        pass

    @abstractmethod
    def extract_relationships(
        self,
        text: str,
        entities: list[Entity] | None = None,
    ) -> list[Relationship]:
        """Extract relations between detected entities."""
        pass


class BaselineEntityExtractor(EntityExtractor):
    """Deterministic Layer 1 baseline entity and relation extractor."""

    KNOWN_ENTITIES = [
        ("krishna", "person"),
        ("కృష్ణ", "person"),
        ("arjuna", "person"),
        ("అర్జున", "person"),
        ("nishkama karma", "concept"),
        ("niṣkāma karma", "concept"),
        ("dharma", "concept"),
        ("భగవద్గీత", "source"),
        ("bhagavad gita", "source"),
        ("dopamine", "neuro_chemical"),
        ("prefrontal cortex", "anatomical_region"),
        ("delay discounting", "psychological_measure"),
    ]

    def extract_entities(self, text: str) -> list[Entity]:
        lower = text.lower()
        entities: list[Entity] = []
        for term, etype in self.KNOWN_ENTITIES:
            start = lower.find(term)
            if start != -1:
                entities.append(Entity(
                    text=text[start:start + len(term)],
                    entity_type=etype,
                    start_char=start,
                    end_char=start + len(term),
                ))
        return entities

    def extract_relationships(
        self,
        text: str,
        entities: list[Entity] | None = None,
    ) -> list[Relationship]:
        ents = entities if entities is not None else self.extract_entities(text)
        names = {e.text.lower() for e in ents}
        relationships: list[Relationship] = []

        if ("krishna" in names or "కృష్ణ" in names) and ("arjuna" in names or "అర్జున" in names):
            relationships.append(Relationship(
                source_entity="Krishna",
                relation_type="teaches",
                target_entity="Arjuna",
                confidence=1.0,
            ))

        if ("nishkama karma" in names or "niṣkāma karma" in names) and "delay discounting" in names:
            relationships.append(Relationship(
                source_entity="Nishkama Karma",
                relation_type="correlates_with",
                target_entity="Reduced Delay Discounting",
                confidence=0.85,
            ))

        return relationships


# ---------------------------------------------------------------------------
# 8. Language-Aware Provider Selection
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProviderLanguageCapability:
    """Language capabilities declared by an inference or reasoning provider."""

    provider_name: str
    supported_languages: list[str]
    supports_direct_telugu: bool = True
    requires_translation: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def select_language_provider(
    providers: list[ProviderLanguageCapability],
    target_language: str,
) -> ProviderLanguageCapability | None:
    """Select the best matching provider based on target language requirements.

    Preserves Telugu-first principle: if target is Telugu, prioritizes providers
    with `supports_direct_telugu = True` to avoid forced translation pivots.

    Args:
        providers: List of declared provider capabilities.
        target_language: Requested language ('telugu', 'english', etc.).

    Returns:
        Best matched ProviderLanguageCapability or None if none eligible.
    """
    if not providers:
        return None

    target = target_language.lower().strip()

    # 1. Exact match with direct language support without translation
    for p in providers:
        if target in p.supported_languages and not p.requires_translation:
            if target == "telugu" and p.supports_direct_telugu:
                return p
            elif target != "telugu":
                return p

    # 2. Match with supported language even if requires translation
    for p in providers:
        if target in p.supported_languages:
            return p

    # 3. Default fallback to first provider
    return providers[0]


# ---------------------------------------------------------------------------
# 9. NLP Provider Abstraction
# ---------------------------------------------------------------------------

class NLPProvider(ABC):
    """Abstract base class uniting NLP capabilities."""

    @abstractmethod
    def identify_language(self, text: str) -> str:
        """Identify language of text."""
        pass

    @abstractmethod
    def normalize_query(self, query: str) -> NormalizedQuery:
        """Normalize query text."""
        pass

    @abstractmethod
    def detect_intent(self, text: str) -> Intent:
        """Classify user intent."""
        pass

    @abstractmethod
    def extract_entities(self, text: str) -> list[Entity]:
        """Extract domain entities."""
        pass


class DefaultNLPProvider(NLPProvider):
    """Concrete Layer 1 standard NLP provider."""

    def __init__(self) -> None:
        self.normalizer = StandardQueryNormalizer()
        self.intent_detector = KeywordIntentDetector()
        self.entity_extractor = BaselineEntityExtractor()

    def identify_language(self, text: str) -> str:
        return detect_language(text)

    def normalize_query(self, query: str) -> NormalizedQuery:
        return self.normalizer.normalize(query)

    def detect_intent(self, text: str) -> Intent:
        return self.intent_detector.detect_intent(text)

    def extract_entities(self, text: str) -> list[Entity]:
        return self.entity_extractor.extract_entities(text)


class MockNLPProvider(NLPProvider):
    """Deterministic mock NLP provider for tests."""

    def __init__(
        self,
        language: str = "english",
        intent: Intent | None = None,
        entities: list[Entity] | None = None,
    ) -> None:
        self._language = language
        self._intent = intent or Intent(intent_id="mock_intent", name="mock_query")
        self._entities = entities or []

    def identify_language(self, text: str) -> str:
        return self._language

    def normalize_query(self, query: str) -> NormalizedQuery:
        return NormalizedQuery(
            original=query,
            normalized=query.strip(),
            script="latin",
            language=self._language,
            tokens=query.strip().split(),
            case_folded=False,
        )

    def detect_intent(self, text: str) -> Intent:
        return self._intent

    def extract_entities(self, text: str) -> list[Entity]:
        return self._entities


# ---------------------------------------------------------------------------
# 10. NLP Evaluation Interfaces
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NLPEvaluationReport:
    """Standard evaluation report for NLP component benchmarks."""

    task: str
    sample_count: int
    accuracy: float
    latency_ms: float
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class NLPEvaluator(ABC):
    """Abstract interface for evaluating NLP components."""

    @abstractmethod
    def evaluate(self, test_cases: list[dict[str, Any]]) -> NLPEvaluationReport:
        """Run evaluation benchmark across provided test cases."""
        pass


class StandardNLPEvaluator(NLPEvaluator):
    """Deterministic Layer 1 evaluation suite for language detection and intent."""

    def __init__(self, provider: NLPProvider | None = None) -> None:
        self.provider = provider or DefaultNLPProvider()

    def evaluate(self, test_cases: list[dict[str, Any]]) -> NLPEvaluationReport:
        """Evaluate provider across test cases.

        Expected test_case schema:
        {"text": str, "expected_language": str, "expected_intent": str (optional)}
        """
        import time

        if not test_cases:
            return NLPEvaluationReport(
                task="nlp_evaluation",
                sample_count=0,
                accuracy=1.0,
                latency_ms=0.0,
                passed=True,
            )

        correct = 0
        t0 = time.perf_counter()

        for case in test_cases:
            txt = case.get("text", "")
            exp_lang = case.get("expected_language")
            exp_intent = case.get("expected_intent")

            match_lang = True
            if exp_lang:
                match_lang = (self.provider.identify_language(txt) == exp_lang)

            match_intent = True
            if exp_intent:
                detected = self.provider.detect_intent(txt)
                match_intent = (detected.name == exp_intent)

            if match_lang and match_intent:
                correct += 1

        t1 = time.perf_counter()
        acc = round(correct / len(test_cases), 3)
        latency = round((t1 - t0) * 1000, 2)

        return NLPEvaluationReport(
            task="nlp_evaluation",
            sample_count=len(test_cases),
            accuracy=acc,
            latency_ms=latency,
            passed=(acc >= 0.8),
            details={"correct": correct, "total": len(test_cases)},
        )
