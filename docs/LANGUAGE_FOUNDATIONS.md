# ANTARĀ — Language & Natural Language Intelligence Foundations
## Telugu-First Architecture & Layer 1 NLP Foundations

---

## 1. Telugu-First Operating Principle

ANTARĀ is established with **Telugu as its foundational language**, with English as an equal primary working language.

Key architectural boundaries:
- **No English Assumption**: Never assume that Latin-script text is English.
- **Romanized Telugu Awareness**: When Telugu is transcribed phonetically using Latin letters (e.g., *"naaku em cheppali?"*), ANTARĀ detects Romanized Telugu patterns and treats the language as mixed/Telugu, refusing to blindly categorize it as English.
- **Direct Reasoning**: Where models support Telugu natively, ANTARĀ avoids forced translation through English pivots.
- **Register Distinction**: Accha Telugu is a vocabulary and literary-register aspiration, not a geographic dialect.

---

## 2. Script vs. Language Distinction

ANTARĀ Layer 1 establishes strict architectural separation between **Script** and **Language**:

1. **Script Identification (`detect_script`)**:
   - Detects the Unicode alphabet block used in the text.
   - Outputs: `Literal["telugu", "latin", "mixed", "none"]`.
   - Telugu Unicode block: `U+0C00` – `U+0C7F`.
   - Latin alphabet: `[A-Za-z]`.
   - Non-alphabetic tokens (digits, punctuation, whitespace) are classified as `none`.

2. **Language Identification (`detect_language`)**:
   - Evaluates the dominant language based on script AND lexical dialect patterns.
   - Outputs: `Literal["telugu", "english", "mixed", "unknown"]`.
   - Pure Telugu script → `"telugu"`.
   - Latin script without Telugu lexical patterns → `"english"`.
   - Latin script with Romanized Telugu lexical patterns → `"mixed"`.
   - Mixed scripts → `"mixed"`.
   - Empty/punctuation-only → `"unknown"`.

---

## 3. The 10 Layer 1 NLP Foundations (`engine.nlp`)

Layer 1 establishes concrete interfaces, data contracts, and deterministic baseline implementations for the 10 Natural Language Intelligence foundations:

| # | NLP Foundation | Contract / Interface | Layer 1 Implementation | Layer 2 Responsibility |
|---|---|---|---|---|
| **1** | **Language Identification** | `detect_script`, `detect_language` | Deterministic script & lexical pattern classifier | Deep neural language classifiers across Indic languages |
| **2** | **Language Metadata Propagation** | `LanguageMetadata`, `extract_language_metadata` | Propagates script, query language, response language, dialect, and code-switching into `IntelligenceBrief` and `UnifiedResponse` | Cross-layer multilingual context propagation |
| **3** | **Intent-Detection Interfaces** | `IntentDetector(ABC)`, `Intent` | `KeywordIntentDetector` classifying philosophical, scientific, comparative, and live web intents | Few-shot & neural intent classification and slot filling |
| **4** | **Query-Normalization Interfaces** | `QueryNormalizer(ABC)`, `NormalizedQuery` | `StandardQueryNormalizer` preserving Telugu Unicode without destructive case folding | Telugu morphological normalization and sandhi splitting |
| **5** | **Semantic-Retrieval Interfaces** | `SemanticRetriever(ABC)`, `SemanticSearchResult` | `MockSemanticRetriever` with score thresholding and top-k filtering | Dense vector embeddings, HNSW index, and hybrid sparse-dense search |
| **6** | **Entity & Relation Extraction** | `EntityExtractor(ABC)`, `Entity`, `Relationship` | `BaselineEntityExtractor` extracting key concepts, deities, persons, and relations (e.g. Krishna teaches Arjuna) | Full Named Entity Recognition (NER) and relation extraction models |
| **7** | **Telugu-English Code-Switching** | `CodeSwitchMetadata`, `detect_code_switching` | Calculates token-level `telugu_ratio`, `latin_ratio`, dominant language, and switch boundary points | Fine-grained code-mixing matrix and intra-sentential parser |
| **8** | **Language-Aware Provider Selection** | `ProviderLanguageCapability`, `select_language_provider` | Prioritizes direct Telugu-supporting providers; forbids forced translation pivots when native processing is supported | Dynamic multi-model routing based on linguistic latency and perplexity |
| **9** | **NLP Provider Abstraction** | `NLPProvider(ABC)` | `DefaultNLPProvider` and `MockNLPProvider` uniting normalization, intent, and entities | Pluggable local and hybrid multilingual NLP backends |
| **10** | **NLP Evaluation Interfaces** | `NLPEvaluator(ABC)`, `NLPEvaluationReport` | `StandardNLPEvaluator` measuring classification accuracy and latency across test cases | Continuous multilingual benchmark suite & automated regression harness |

---

## 4. Dialect & Register Registry (`identify_dialect`)

Layer 1 includes an extensible dialect registry stub (`_DIALECTS`) designed for extension in Layer 2:

- **Classical / Literary Telugu (`classical`)**: Historic and scriptural vocabulary (e.g., *దుర్గాపురాణ*, *శైవశాస్ర్త్ర*).
- **Vyavaharika Telugu (`vyavaharika`)**: Modern spoken idiom (e.g., *చెప్పుద్దాం*, *ఎయితే*).
- **Romanized Telugu (`romanized`)**: Telugu written in Latin alphabet (e.g., *naaku*, *emi*, *chaala*).

Word boundaries in Telugu Unicode regexes account for Telugu vowel signs, viramas, and conjunct characters using Unicode-aware boundary classes (`[^\w\u0C00-\u0C7F]`).

---

## 5. Scope Boundaries: Layer 1 vs. Layer 2

- **Layer 1 Scope**: Defines stable interfaces, data classes, baseline rule-based implementations, deterministic mock providers, and end-to-end metadata propagation.
- **Layer 2 Scope**: Implements substantial linguistic intelligence:
  - Deep Telugu tokenizers, sentence segmenters, stemmers, and lemmatizers.
  - Part-of-Speech (POS) tagging and dependency parsing.
  - Comprehensive Telugu morphology (vibhakti, sandhi, samasa).
  - Neural Named Entity Recognition (NER).
  - Telugu semantic vector embeddings and dense retrieval.
  - Dialect classifiers for Telangana, Coastal Andhra, Rayalaseema, and Uttarandhra varieties.
  - Accha Telugu vocabulary analyzer.
