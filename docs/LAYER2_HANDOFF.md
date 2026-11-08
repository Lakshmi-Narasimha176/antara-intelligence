# ANTARĀ — Layer 2 Engineering Handoff Document

This document provides the formal handoff specifications from **Layer 1: Core Intelligence & Advanced Reasoning** to **Layer 2: Universal Knowledge, Language & Perception**.

---

## 1. Stable Layer 1 Interfaces Available for Layer 2

Layer 2 components can depend on the following verified, stable interfaces:

### A. Orchestration & Planning
- `engine.orchestrator.create_brief(question, ...)` → Returns `IntelligenceBrief` populated with subsystem plan, validated contexts, language metadata, and code-switching metrics.
- `engine.orchestrator.classify_subsystems(question)` → Subsystem routing logic for traditional knowledge, empirical research, and live internet.
- `engine.unified_engine.UnifiedEngine` → Top-level orchestrator coordinating end-to-end question processing, fact checking, and governance.

### B. Language & NLP Foundations (`engine.language`, `engine.nlp`)
- **Language & Script**:
  - `detect_script(text)` → Script detection (`telugu`, `latin`, `mixed`, `none`).
  - `detect_language(text)` → Language categorization (`telugu`, `english`, `mixed`, `unknown`).
  - `identify_dialect(text)` → Extensible dialect recognition stub (`classical`, `vyavaharika`, `romanized`).
- **Code-Switching & Metadata**:
  - `detect_code_switching(text)` → Returns `CodeSwitchMetadata` with token ratios (`telugu_ratio`, `latin_ratio`) and switch points.
  - `extract_language_metadata(text, ...)` → Returns comprehensive `LanguageMetadata`.
- **Query Normalization**:
  - `QueryNormalizer(ABC)` / `StandardQueryNormalizer` → Normalizes query preserving Telugu Unicode.
- **Intent Detection**:
  - `IntentDetector(ABC)` / `KeywordIntentDetector` → Intent classification into philosophical, scientific, comparative, live web, or general domains.
- **Semantic Retrieval**:
  - `SemanticRetriever(ABC)` / `MockSemanticRetriever` / `SemanticSearchResult` → Dense retrieval contract.
- **Entity & Relationship Extraction**:
  - `EntityExtractor(ABC)` / `BaselineEntityExtractor` / `Entity` / `Relationship` → Domain entity and semantic relationship extractor.
- **Language-Aware Provider Selection**:
  - `select_language_provider(providers, target_lang)` / `ProviderLanguageCapability` → Prioritizes direct native processing over forced translation.
- **NLP Provider Abstraction**:
  - `NLPProvider(ABC)` / `DefaultNLPProvider` / `MockNLPProvider` → Unified NLP driver interface.
- **NLP Evaluation**:
  - `NLPEvaluator(ABC)` / `StandardNLPEvaluator` / `NLPEvaluationReport` → Accuracy and latency benchmark harness.

### C. LLM Provider Abstraction
- `engine.llm_provider.LLMProvider` → Abstract base class for reasoning engines.
- `engine.llm_provider.MockLLMProvider` → Deterministic fixture for offline testing.
- `engine.ollama_provider.OllamaProvider` → Local Ollama integration (`GET /api/tags`, `POST /api/generate`).
- `engine.openai_provider.OpenAIProvider` → Optional cloud provider.

### D. Knowledge, Research & Retrieval
- `engine.knowledge.KnowledgeBase` → SQLite storage, verse versioning, SHA-256 integrity hashes, human verification records.
- `engine.research.ResearchManager` → Peer-reviewed research papers, DOI deduplication, evidence categorization.
- `engine.search.SearchManager` → Live web querying, SSRF defense, robots.txt compliance, bounded LRU caching.
- `engine.fact_checker.FactChecker` → Deterministic claim validation, quote verification, and hallucination scoring.

### E. Human-in-the-Loop Governance
- `engine.governance.GovernanceEngine` → 9-state report lifecycle, cryptographic approval binding, publication authorization.
- `engine.unified_response.UnifiedResponse` → Comprehensive 12-dimensional output schema including `language_metadata`.

---

## 2. Integration Points for Layer 2

Layer 2 will build upon Layer 1 at the following key integration points:

1. **Multilingual & Perception Tokenizers**:
   - Subclass `QueryNormalizer` and implement deep phonological transliteration (Telugu script ↔ Romanized Latin / ISO 15919).
2. **Advanced Semantic Vector Retrieval**:
   - Subclass `SemanticRetriever` to connect embedding models (e.g., IndicBERT, Sentence-Transformers) to dense vector indices.
3. **Deep NLU & Morphology**:
   - Subclass `EntityExtractor` and `IntentDetector` with neural models for comprehensive Telugu morphology (vibhakti, sandhi, samasa).
4. **Universal Ontology & Knowledge Graph**:
   - Connect `engine.knowledge` database tables into a graph representation spanning philosophical, scientific, and linguistic concepts.
5. **Multimodal Providers**:
   - Extend `LLMProvider` to support vision, audio, and sensor perception inputs without breaking text generation contracts.

---

## 3. Compatibility & Non-Negotiable Constraints

1. **Local-First Mandate**: Layer 2 must preserve offline operation and not mandate cloud API keys.
2. **Zero Invalidation of Layer 1 Tests**: All existing Layer 1 tests must continue to pass without modification.
3. **Memory Footprint**: Target compact runtime (RAM RSS < 150 MB for core services, excluding local neural weights).
4. **Append-Only Governance**: Never bypass human verification or exact-content approval safeguards.
