# ANTARĀ Intelligence Engine v1

**ANTARĀ Intelligence Engine** is a human-supervised AI intelligence architecture designed to turn complex human inquiries into structured, source-traceable, and rigorously verified intelligence briefs.

> **Human-in-the-Loop Mandate:**
> The system strictly enforces human supervision (`human_review_required: true`). Under no circumstances may AI models fabricate sources, quotations, translations, or test results. Human approval is mandatory before any research conclusion is accepted or published.

---

## 1. Quickstart (Windows 10 / VS Code / PowerShell)

### Prerequisites
- Windows 10 (or later)
- Python 3.12 (`py -3.12 --version`)
- Visual Studio Code

### PowerShell Setup Instructions

Open this folder in VS Code. In **Terminal → New Terminal (PowerShell)**, run:

```powershell
# 1. Verify Python 3.12 is available
py -3.12 --version

# 2. Create the virtual environment
py -3.12 -m venv .venv

# 3. If script execution is blocked on Windows, set execution policy for the process
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 4. Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# 5. Set terminal output encoding to UTF-8 for multilingual text & diacritics
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 6. Verify virtual environment python
python --version

# 7. Run the test suite
python -m unittest discover -s tests -v

# 8. Run the CLI entry point
python app.py "Why do people procrastinate even when they know what matters?"

# 9. Test multilingual & philosophical query support
python app.py "What does dharma (धर्म) and karma-yoga mean in the Bhagavad Gītā?"
```

Expected output:
- All unit tests pass cleanly.
- `app.py` displays the structured brief to stdout and writes the JSON artifact to `outputs/latest_brief.json`.

---

## 2. Engineering Standards

The codebase adheres to the following production engineering standards:

1. **Python 3.12 Compatibility:** Uses standard language features and type annotations compatible with Python 3.12+.
2. **Type Hints:** All public functions, dataclasses, and methods carry comprehensive type annotations.
3. **Docstrings:** All modules, classes, and methods are documented following Google/PEP 257 docstring conventions.
4. **Single-Responsibility Modules:** Strict separation between CLI presentation (`app.py`), domain orchestration (`engine/orchestrator.py`), and future specialized modules.
5. **Pathlib Everywhere:** All filesystem operations use `pathlib.Path` with explicit UTF-8 encoding.
6. **UTF-8 Multilingual Support:** End-to-end UTF-8 encoding for console streams, file reading, and file writing to support Sanskrit diacritics (IAST like *Gītā*, *dharma*) and Devanagari script (धर्म).
7. **Explicit Exceptions:** Domain-specific exceptions (`AntaraError`, `ValidationError`, `QuestionTypeError`) that inherit from standard exceptions for complete backward compatibility.
8. **Environment Variables for Secrets:** Zero hardcoded credentials or API keys; configurations are read from environment variables or `.env` templates (`.env.example`).
9. **Unit Tests:** High coverage using standard library `unittest` with explicit assertions and zero external test runners required.
10. **Structured Logging:** Standardized logging with timestamps, severity levels, and module names, controllable via `ANTARA_LOG_LEVEL`.
11. **Minimal Dependencies:** Zero runtime third-party dependencies for core operations; standard library first.

---

## 3. Current Architecture & Modules

### Module 1: Orchestration & Research Briefs
- **Entry Point:** `app.py` - CLI argument parsing, UTF-8 console stream configuration, brief generation, and persistence to `outputs/latest_brief.json`.
- **Orchestrator:** `engine/orchestrator.py` - Question validation, boundary constraints, topic classification, and frozen `IntelligenceBrief` generation.
- **Unit Tests:** `tests/test_orchestrator.py` - 12 tests validating normalization, error boundaries, explicit exception hierarchy, and multilingual UTF-8 question processing.

### Module 2: Knowledge Intelligence (Bhagavad Gītā Repository)
- **Engine Core:** `engine/knowledge.py` - SQLite3-backed normalized repository with foreign keys, constraints, SHA-256 fingerprinting, tamper detection, controlled JSON importer, and append-only audit trail.
- **CLI Interface:** `engine/knowledge_cli.py` - Command-line tools for DB initialization, JSON imports, verse retrieval (displaying Sanskrit, transliteration, translation, and source metadata together), search, human review recording, audit trails, and integrity checks.
- **Unit Tests:** `tests/test_knowledge.py` - 17 unit tests covering schema creation, source normalization, verse constraints, duplicate rejection, UTF-8 preservation, dry-run imports, partial failure handling, human verification transitions, substantive evidence enforcement, content modification invalidation, and tamper detection.
- **Runtime Database:** `data/antara_knowledge.db` - Local SQLite database storing normalized bibliographic sources, verses, and append-only audit records.

### Knowledge Retrieval Bridge (Module 1 ↔ Module 2 Integration)
- **Bridge Core:** `engine/retrieval.py` - Semantic and citation routing, verified-only querying, defense-in-depth cryptographic integrity checks, and graceful fallbacks.
- **Orchestrator Integration:** `engine/orchestrator.py` - Enriches `IntelligenceBrief` with an immutable `knowledge_context` field containing verified primary source records when philosophical inquiry is indicated.
- **CLI Presentation:** `app.py` - Displays verified primary sources and source provenance directly alongside the research brief.
- **Unit Tests:** `tests/test_retrieval.py` - 14 unit tests covering verified retrieval, unreviewed/rejected/tampered record exclusion, provenance preservation, empty search results, non-philosophical query routing, missing database resilience, and backward compatibility.

### Module 3: Research Intelligence (Academic & Empirical Evidence)
- **Engine Core:** `engine/research.py` - Provider-independent research retrieval layer, normalized DOI deduplication, quad-category evidence classification (`supporting`, `contradicting`, `contextual`, `inconclusive`), SHA-256 cryptographic fingerprinting, and substantive human review workflow.
- **CLI Interface:** `engine/research_cli.py` - Command-line tools for initializing research tables, querying sources and claims, adding/classifying evidence, recording human verification decisions (`approved`/`rejected`), viewing append-only audit histories, and batch JSON imports.
- **Unit Tests:** `tests/test_research.py` - 16 unit tests covering source insertion, DOI/metadata deduplication, evidence classification, provider timeout/resilience handling, substantive human review requirements, audit logging, and Module 1/2 integration.
- **Database Tables:** `research_sources`, `research_evidence`, `research_audit` in `data/antara_knowledge.db`.

### Module 4: Anti-Hallucination & Fact-Checking Engine
- **Engine Core:** `engine/fact_checker.py` - Deterministic, evidence-grounded validation engine that checks whether claims, quotations, source references, and citations are supported by authenticated knowledge records and approved research evidence.
- **CLI Interface:** `engine/fact_checker_cli.py` - Command-line tools for batch claims validation (`validate`), single Gita quotation checks (`check-gita`), and report generation.
- **Unit Tests:** `tests/test_fact_checker.py` - 17 unit tests covering valid source references, missing citations, unreviewed/rejected records, SHA-256 tamper detection, exact vs. mismatched quotations, approved vs. rejected empirical evidence, contradiction detection, schema validation, empty collections, database failures, and orchestrator integration.

### AI Reasoning Engine & LLM Providers
- **Provider Layer:** `engine/llm_provider.py` & `engine/openai_provider.py` - Provider-independent reasoning architecture with official OpenAI SDK support, configurable timeout, limited retries, refusal/truncation handling, and offline `MockLLMProvider`.
- **Context Builder:** `engine/context_builder.py` - Assembles strictly bounded, provenance-preserving contexts containing verified Gītā verses and approved empirical evidence, filtering out unreviewed or tampered data.
- **Reasoning Core:** `engine/reasoning.py` - Generates 16-dimensional philosophical-scientific syntheses, rejects fabricated IDs, catches forbidden claims, and enforces Module 4 validation.
- **CLI Interface:** `engine/reasoning_cli.py` - Command-line tools for synthesis (`synthesize`), human review recording (`review`), and report inspection (`get`).
- **Unit Tests:** `tests/test_reasoning.py` - 14 unit tests covering provider abstraction, client-injected response normalization, error translation, timeout/retry/refusal handling, context filtering, lifecycle state transitions, and Module 4 validation gating.
- **Database Tables:** `reasoning_reports`, `reasoning_audit` in `data/antara_knowledge.db`.

### Module 5: Human-in-the-Loop (HITL) Governance & Publishing Pipeline
- **Engine Core:** `engine/governance.py` - Manages a strict 9-state report lifecycle (`generated`, `validation_failed`, `pending_review`, `approved`, `rejected`, `revision_requested`, `ready_to_publish`, `published`, `archived`), version snapshots, append-only audit trail, SHA-256 fingerprint matching, tamper invalidation, and pluggable publishing providers (`PublishingProvider`, `LocalFilePublisher`, `MockPublishingProvider`).
- **CLI Interface:** `engine/governance_cli.py` - Command-line tools for report lifecycle management (`status`, `review`, `authorize`, `publish`, `export`, and `audit`).
- **Unit Tests:** `tests/test_governance.py` - 14 unit tests covering the full lifecycle progression, invalid state transition rejections, unvalidated approval blocking, substantive notes enforcement, post-approval tamper detection, fingerprint mismatch guards, duplicate publication prevention, immutable audit history, and multi-format exports.
- **Database Tables:** `governance_records`, `governance_versions`, `governance_audit`, `governance_publications` in `data/antara_knowledge.db`.

### Real-Time Internet Intelligence (Part A)
- **Engine Core:** `engine/search.py` - Pluggable live web retrieval architecture with `SearchProvider` ABC, `MockSearchProvider`, `OpenAIWebSearchProvider`, source credibility scoring, URL deduplication, semantic conflict detection, publication vs. retrieval date separation, robots.txt compliance, SSRF protection, and prompt injection sanitization.
- **CLI Interface:** `engine/search_cli.py` - Command-line tools for live and mock web searches (`search`), page text extraction (`fetch`), and robots policy inspection (`check-robots`).
- **Unit Tests:** `tests/test_search.py` - 14 unit tests covering providers, deduplication, conflict analysis, dates, SSRF blocking, injection defusing, rate limits, timeouts, and caching.

### Unified Intelligence Engine & 12-Dimensional Response System (Layer 1 Core)
- **Engine Core:** `engine/unified_engine.py` & `engine/unified_response.py` - Orchestrates the entire Layer 1 pipeline: intelligent subsystem routing (`classify_subsystems`), verified Gītā retrieval, approved research evidence, live web search, AI reasoning, Module 4 validation gating, Module 5 governance registration, and 12-dimensional `UnifiedResponse` generation.
- **Unit Tests:** `tests/test_unified_orchestrator.py` & `tests/test_live_smoke.py` - 14 comprehensive integration tests covering all Part F scenarios offline, plus 3 on-demand live internet & API smoke tests.

---

## 4. Module 2: Knowledge Intelligence CLI & Workflow

### Virtual Environment Activation (Windows PowerShell)

Always ensure your virtual environment is active before executing CLI commands:

```powershell
# In PowerShell:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

### PowerShell Command Examples

```powershell
# 1. Initialize the SQLite database schema
python -m engine.knowledge_cli init-db

# 2. Run a dry-run import test
python -m engine.knowledge_cli import --file examples/sample_verses.json --dry-run

# 3. Perform a real import (leaves all new records as 'unreviewed')
python -m engine.knowledge_cli import --file examples/sample_verses.json

# 4. Display a verse with Sanskrit, transliteration, translation, and source provenance
python -m engine.knowledge_cli get --chapter 2 --verse 47

# 5. Search verses by keyword
python -m engine.knowledge_cli search --query "action"

# 6. Retrieve verified-only verses (excludes unreviewed or tampered records)
python -m engine.knowledge_cli search --chapter 2 --verified-only

# 7. Record a human verification decision with substantive evidence
python -m engine.knowledge_cli review `
  --verse-id 1 `
  --decision verified `
  --reviewer "Dr. S. Sharma (Sanskrit Philology)" `
  --evidence "Collated with Bhandarkar Oriental Research Institute (BORI) Critical Edition Vol 7, p. 88; verified against Shankaracharya Bhashya 2.47." `
  --locator "BORI Vol. 7, p. 88"

# 8. View append-only audit trail for a verse
python -m engine.knowledge_cli audit --verse-id 1

# 9. Verify cryptographic integrity across the entire database
python -m engine.knowledge_cli verify-integrity

# 10. Explain mechanical vs. human verification
python -m engine.knowledge_cli explain-verification
```

---

## 5. Knowledge Retrieval Bridge & Integrated Execution

### Architecture: Connecting Module 1 to Module 2

The Knowledge Retrieval Bridge ([`engine/retrieval.py`](file:///c:/Users/ln123/Documents/LN/Coding/My%20Projects/Antara%20Intelligence/engine/retrieval.py)) links the question orchestrator with the knowledge repository through four strictly controlled stages:

```
[User Question]
       │
       ▼
[1. Routing Gate: should_retrieve_knowledge()]
  ├── Topic == 'philosophy'? ──► Retrieval Indicated
  ├── Gita Keywords / BG Citations? ──► Retrieval Indicated
  └── Non-Philosophical (e.g. Behavior/Tech)? ──► Retrieval Bypassed (empty collection returned)
       │
       ▼ (if indicated)
[2. Query Formulation]
  ├── Explicit Verse Reference (e.g. 'Chapter 2, Verse 47' or 'BG 2.47')
  └── Keyword Extraction (filters out stop words)
       │
       ▼
[3. Verified-Only Query & Integrity Filtering]
  ├── KnowledgeBase.search_verses(verified_only=True)
  ├── Excludes unreviewed, rejected, and invalidated records
  └── Cryptographic check: compute_content_hash(...) == record.content_hash
       │
       ▼
[4. Brief Enrichment (IntelligenceBrief)]
  └── Attaches verified primary source records into 'knowledge_context'
```

### Running the Integrated Application

Run the integrated application directly with PowerShell:

```powershell
# Activate the virtual environment
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 1. Run integrated application with a philosophical inquiry (attaches verified Gita knowledge)
python app.py "What does the Bhagavad Gita teach in Chapter 2, Verse 47 about action and fruits?"

# 2. Run with an ordinary non-philosophical inquiry (retrieval safely bypassed)
python app.py "Why do people procrastinate even when they know what matters?"

# 3. Run the full 135-test Layer 1 suite (132 passing, 3 skipped offline)
python -m unittest discover -s tests -v
```

---

## 6. Module 3: Research Intelligence CLI & Workflow

### Overview & Philosophy
Module 3 establishes a rigorous research intelligence layer for academic and empirical studies across psychology, neuroscience, cognitive science, and philosophy:
- **Zero Fabrication:** No papers, authors, DOIs, URLs, or empirical findings may be invented.
- **Provider Independence:** Pluggable `ResearchProvider` abstract base class supporting diverse providers (`MockResearchProvider` used offline, with adapters for CrossRef, Semantic Scholar, OpenAlex, etc.).
- **Evidence Quad-Classification:** Every empirical finding or claim is explicitly mapped to the core inquiry:
  - `supporting`: Corroborates the hypothesis or inquiry.
  - `contradicting`: Challenges or refutes the hypothesis.
  - `contextual`: Provides relevant background, methodology, or situational nuances.
  - `inconclusive`: Preliminary, underpowered, or mixed findings.
- **Deduplication:** Automatic collision detection via normalized DOI and composite key `(normalized_title, first_author, publication_year)`.
- **Substantive Human Review:** Every imported research study and claim begins in `unreviewed` state. Promotion to `approved` or transition to `rejected` strictly requires a named reviewer and a substantive rationale ($\ge 15$ characters).

### SQLite Research Tables
Within `data/antara_knowledge.db`:
- `research_sources`: Stores bibliographic metadata (DOI, title, authors, journal, year, URL, abstract, methodology, sample size, limitations, verification status, SHA-256 hash).
- `research_evidence`: Normalizes specific empirical findings, associated variables, effect sizes, statistical significance, and quad-classification against research topics.
- `research_audit`: Append-only audit trail capturing every review decision, reviewer identity, timestamp, and rationale.

### PowerShell Command Examples

```powershell
# 1. Initialize the research database tables
python -m engine.research_cli init-db

# 2. Search research sources by keyword
python -m engine.research_cli search-sources --query "temporal motivation"

# 3. Inspect a research source by ID with methodology & limitations
python -m engine.research_cli get-source --source-id 1

# 4. Search and view classified evidence findings
python -m engine.research_cli search-evidence --classification supporting

# 5. Classify a new empirical claim under a research source
python -m engine.research_cli classify `
  --source-id 1 `
  --topic "Temporal Motivation Theory and Task Delay" `
  --claim "Procrastination correlates strongly with impulsiveness and task delay discounting (r = 0.41)." `
  --classification supporting `
  --strength strong `
  --effect-size "r = 0.41" `
  --significance "p < .001"

# 6. Human review and approval of a research source
python -m engine.research_cli review-source `
  --source-id 1 `
  --decision approved `
  --reviewer "Dr. E. Vance, Cognitive Psychology" `
  --notes "Meta-analysis methodology verified against PRISMA guidelines; sample size N=212 exceeds power requirements."

# 7. Human review and approval of an evidence claim
python -m engine.research_cli review-evidence `
  --evidence-id 1 `
  --decision approved `
  --reviewer "Dr. E. Vance, Cognitive Psychology" `
  --notes "Statistical effect size verified from Table 3 in published Psychological Bulletin paper."

# 8. View append-only audit trail for research records
python -m engine.research_cli audit --target-type source --target-id 1

# 9. Import research sources from a UTF-8 JSON file
python -m engine.research_cli import --file examples/sample_research.json
```

---

## 7. Module 4: Anti-Hallucination & Fact-Checking Engine

### Overview & Philosophy
Module 4 introduces an evidence-grounded, anti-hallucination validation engine that deterministically audits claims, quotations, source references, and citations produced by or submitted to ANTARĀ.

```
[User Question]
       │
       ▼
[Intelligence Orchestrator]
       │
       ├─► [Verified Gita Retrieval] ─────────────┐
       │                                          ▼
       └─► [Approved Research Retrieval] ─► [Structured Claim Package]
                                                  │
                                                  ▼
                                      [Fact-Checking Engine]
                                                  │
                                                  ▼
                                      [Fact-Check Report]
                                                  │
                                                  ▼
                                      [Mandatory Human Review]
```

### Core Invariants:
1. **Never Assume AI Correctness:** An LLM is never the authority for factual verification. All checks evaluate against cryptographically verified primary sources and peer-reviewed empirical research in SQLite.
2. **Source Integrity ≠ Factual Correctness:** A computer check verifying that a citation ID exists or that a SHA-256 hash matches only confirms *mechanical provenance*. It does **not** prove theological, historical, or scientific truth.
3. **Preserve Contradictions & Uncertainty:** When literature contains conflicting findings (e.g. impulsiveness vs. perfectionism in delay discounting), the engine explicitly identifies contradicting records and flags the claim as `contradicted`, preventing one-sided confirmation bias.
4. **Quotations vs. Paraphrases:** Exact quotations are mechanically verified against Sanskrit, transliteration, or translation text. Paraphrases and conceptual summaries are categorized as `partially_supported` and flagged with `paraphrase_requires_human_assessment`.

### Deterministic Claim Statuses

| Status | Deterministic Criteria |
| :--- | :--- |
| `source_verified` | Verified Gita verse or approved research finding; SHA-256 hash intact; exact or whitespace-normalized quotation matches source text without contradictions. |
| `partially_supported` | Authenticated source exists and passes hash check, but the claim is a paraphrase, excerpt, or notes methodological limitations in the underlying empirical study. |
| `unsupported` | No source cited, referenced ID/DOI does not exist in repository, or direct quotation does not match stored text. |
| `contradicted` | Approved evidence record with `classification == 'contradicting'` exists on the same topic/source. |
| `insufficient_evidence` | Referenced research source or evidence is unreviewed, or evidence has `low`/`exploratory` strength or unverified sample size. |
| `requires_human_review` | Interpretive hypotheses, unreviewed verses, or tampered records requiring scholarly human arbitration. |

### Fact-Checking Report Schema (`FactCheckReport`)

Reports are serialized to JSON with the following structure:
```json
{
  "report_id": "fc_20261108_044718_fad414fd",
  "brief_id": "brief_procrastination_1",
  "timestamp_utc": "2026-11-08T04:47:18.444542+00:00",
  "overall_status": "FAILED_UNSUPPORTED",
  "total_claims": 5,
  "verified_claims": 1,
  "partially_supported_claims": 1,
  "unsupported_claims": 3,
  "contradicted_claims": 0,
  "insufficient_evidence_claims": 0,
  "requires_human_review_claims": 0,
  "claims": [
    {
      "claim_id": "claim_gita_quote_authentic",
      "claim_text": "To action alone hast thou a right...",
      "status": "source_verified",
      "reasons": ["Direct quotation exactly verified against authenticated verse."],
      "source_exists": true,
      "source_verified": true,
      "integrity_valid": true,
      "is_direct_quote": true,
      "quote_matches": true,
      "referenced_source_id": 1,
      "referenced_record_id": 1,
      "flags": [],
      "human_review_required": true
    }
  ],
  "supporting_sources": [
    {
      "type": "gita",
      "id": 1,
      "title": "The Bhagavadgita",
      "author": "Dr. S. Radhakrishnan"
    }
  ],
  "contradicting_sources": [],
  "missing_citations": ["claim_missing_citation"],
  "integrity_failures": [],
  "unresolved_questions": [],
  "human_review_required": true,
  "summary_notes": "Validated 5 claim(s): 1 verified, 1 partially supported, 3 unsupported..."
}
```

### PowerShell Command Examples

```powershell
# 1. Validate a batch of claims from a JSON file
python -m engine.fact_checker_cli validate --file examples/sample_claims.json

# 2. Check an individual Bhagavad Gita quotation
python -m engine.fact_checker_cli check-gita `
  --chapter 2 `
  --verse 47 `
  --quote "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।" `
  --field sanskrit

# 3. Run the end-to-end pipeline with claims validation
python app.py "What does the Bhagavad Gita teach in Chapter 2, Verse 47?" --claims-file examples/sample_claims.json
```

---

## 8. AI Reasoning Engine & OpenAI Provider Architecture

### Overview & Pipeline
The AI Reasoning Engine combines authenticated primary scripture (Bhagavad Gītā) and approved modern research (psychology, neuroscience) to generate deep philosophical-scientific syntheses:

```
[User Question]
       │
       ▼
[Intelligence Orchestrator] ──► [Context Builder] (filters verified & approved records only)
                                      │
                                      ▼
                            [LLM Provider Layer] (OpenAI / MockLLMProvider)
                                      │
                                      ▼
                            [Structured 16-D JSON]
                                      │
                                      ▼
                         [Module 4 Fact-Checking Audit]
                                      │
               ┌──────────────────────┴──────────────────────┐
               ▼                                             ▼
     [FAILED / COMPROMISED]                        [PASSED VERIFIED]
               │                                             │
               ▼                                             ▼
    Status: validation_failed                     Status: pending_review
    (Approval Strictly Blocked)                              │
                                                             ▼
                                                [Human Review Workflow]
                                                (Approved or Rejected)
```

### Core Invariants:
1. **Never Claim Science "Proves" the Gītā:** Treats primary scripture and empirical science as distinct epistemological frameworks with distinct ontologies and truth criteria.
2. **Strict Provenance & Zero ID Invention:** Models may only reference explicit `GITA_VERSE_ID` and `RESEARCH_EVIDENCE_ID` identifiers present in the bounded context.
3. **Module 4 Validation Gate:** Any generated report referencing fabricated IDs, failing quote matching, or asserting forbidden proof claims enters `validation_failed`.
4. **Controlled Lifecycle States:** `generated` $\rightarrow$ `validation_failed` (terminal until regenerated) OR `pending_review` $\rightarrow$ `approved` / `rejected`. Reports in `validation_failed` cannot be approved.
5. **No Automatic Publishing:** All outputs require human supervision (`human_review_required = True`).

### OpenAI Configuration & Environment Variables
Configured via environment variables (`.env.example` provided; `.env` is git-ignored):

| Variable | Description | Default |
| :--- | :--- | :--- |
| `OPENAI_API_KEY` | Official OpenAI API Key (`sk-...`). **Never hardcode or commit.** | *None* |
| `OPENAI_MODEL` | Target OpenAI model identifier. | `gpt-4o-mini` |
| `OPENAI_TIMEOUT` | Request timeout in seconds. | `30.0` |
| `OPENAI_MAX_RETRIES` | Maximum retry attempts on transient network errors. | `2` |

### 16-Dimensional Output Schema (`ReasoningAnalysis`)
1. `executive_summary`: High-level synthesis.
2. `philosophical_perspective`: Systematic Bhagavad Gītā framework.
3. `relevant_gita_teachings`: Verses cited with Sanskrit and translation.
4. `modern_scientific_perspectives`: Contemporary psychological/cognitive paradigms.
5. `supporting_research_evidence`: Corroborating empirical studies.
6. `contradicting_research_evidence`: Conflicting studies and boundary conditions.
7. `philosophical_and_scientific_similarities`: Conceptual convergences.
8. `important_differences`: Ontological and methodological distinctions.
9. `critical_analysis`: Rigorous comparative evaluation.
10. `original_synthesized_insight`: Novel synthesis respecting domain boundaries.
11. `practical_implications`: Actionable real-world guidance.
12. `limitations_and_uncertainty`: Epistemic and methodological caveats.
13. `research_gaps`: Unresolved empirical and philosophical questions.
14. `exact_source_citations`: Explicit provenance mappings.
15. `claims_requiring_human_review`: Discrete factual/interpretive claims submitted to Module 4.
16. `validation_report`: Complete Module 4 audit log.

### PowerShell Command Examples

```powershell
# 1. Execute reasoning synthesis offline using MockLLMProvider
python -m engine.reasoning_cli synthesize "What does the Bhagavad Gita teach in Chapter 2, Verse 47?" --mock

# 2. Review and record human approval on a pending report
python -m engine.reasoning_cli review `
  --report-id "reason_20261108_052517_bae379e8" `
  --decision approved `
  --reviewer "Dr. S. Radhakrishnan" `
  --notes "Scholarly review confirms Niṣkāma Karma synthesis and valid comparative methodology."

# 3. Inspect a persisted reasoning report and review audit trail
python -m engine.reasoning_cli get --report-id "reason_20261108_052517_bae379e8"

# 4. Run end-to-end question analysis with reasoning synthesis
python app.py "What does the Bhagavad Gita teach in Chapter 2, Verse 47?" --reason --mock-llm

# 5. Controlled Live API Smoke-Test (Requires valid OPENAI_API_KEY in environment)
$env:OPENAI_API_KEY = "sk-..."
$env:OPENAI_MODEL = "gpt-4o-mini"
python -m engine.reasoning_cli synthesize "What does the Bhagavad Gita teach in Chapter 2, Verse 47?"
```

---

## 9. Module 5: HITL Governance & Publishing Pipeline CLI & Workflow

### Overview & Philosophy
Module 5 implements a secure, auditable, human-controlled governance system managing AI-generated reports and syntheses from generation through review, authorization, and publication.

> **Absolute Safeguard:**
> No AI-generated content can ever be published automatically or without explicit human authorization. The system mechanically rejects any attempt to publish unapproved, unreviewed, or tampered material.

```
[Generated Synthesis]
        │
        ▼
[Module 4 Fact-Check Gate]
  ├── Failed Validation ──► [validation_failed] (Approval Strictly Blocked)
  └── Passed Validation ──► [pending_review]
                                   │
                                   ▼
                       [Human Review Workflow]
                         ├── Reject ──────────► [rejected]
                         ├── Request Revision ─► [revision_requested]
                         └── Approve ─────────► [approved]
                                                   │
                                                   ▼
                                     [Human Publish Authorization]
                                       ├── SHA-256 Hash Verification
                                       ├── Explicit Authorizer & Channel
                                       └── Transitions to [ready_to_publish]
                                                   │
                                                   ▼
                                         [Publishing Pipeline]
                                           ├── LocalFilePublisher (JSON + Markdown)
                                           └── Transitions to [published]
                                                   │
                                                   ▼
                                              [archived]
```

### Report Lifecycle State Machine

The Governance Engine enforces 9 mutually exclusive lifecycle states with strict transition constraints:

| State | Permitted Transitions | Guard Invariants |
| :--- | :--- | :--- |
| `generated` | `validation_failed`, `pending_review` | Automatically evaluated against Module 4 validation. |
| `validation_failed` | `archived` | Cannot be approved or published; requires complete regeneration. |
| `pending_review` | `approved`, `rejected`, `revision_requested`, `archived` | Requires named human reviewer and substantive notes ($\ge 20$ chars). |
| `approved` | `ready_to_publish`, `revision_requested`, `archived` | SHA-256 fingerprint frozen at approval time (`approved_hash`). |
| `rejected` | `archived` | Terminal review outcome. |
| `revision_requested` | `pending_review`, `archived` | Increments version snapshot; resets approval state. |
| `ready_to_publish` | `published`, `archived` | Requires explicit authorizer identity and channel authorization. |
| `published` | `archived` | Tamper-proof export to filesystem or provider. Duplicate publication blocked. |
| `archived` | *(None - Terminal)* | Preserved for historical and audit reference. |

### Supported Content Types
The pipeline manages 6 distinct content formats:
1. `philosophical_analysis`: In-depth scriptural and philosophical exegesis.
2. `scientific_research_comparison`: Comparative cross-epistemic research evaluations.
3. `gita_based_insights`: Verse-grounded practical wisdom and ethics.
4. `educational_article`: Long-form explanatory essays for broader audiences.
5. `social_media_draft`: Bounded, citation-annotated short-form synthesis.
6. `long_form_report`: Exhaustive multi-disciplinary intelligence monographs.

### Publishing Safeguards & Defense-in-Depth
- **Cryptographic Fingerprint Validation:** Every report content payload has its canonical SHA-256 hash computed (`compute_governance_hash`).
- **Post-Approval Tamper Invalidation:** If database content is altered after human approval, `current_hash != approved_hash`, and publishing is immediately blocked with `FingerprintMismatchError`.
- **Duplicate Publication Guard:** The publisher tracks published versions per channel; attempting to publish the same version twice raises `DuplicatePublicationError`.
- **Append-Only Audit History:** Every review, revision, authorization, and publication step writes an immutable audit record to `governance_audit`.

### Multi-Channel Publishing Architecture
- **`PublishingProvider` (ABC):** Extensible base class for all publication destinations.
- **`LocalFilePublisher`:** Generates verified publication artifacts:
  - **JSON Export:** Full machine-readable envelope with metadata, hashes, versions, citations, and provenance.
  - **Publication-Grade Markdown:** Clean, publication-ready Markdown article complete with title, summary, Gita teachings, empirical science, comparative synthesis, and full bibliographic citations.
- **`MockPublishingProvider`:** Deterministic in-memory provider for zero-network testing.

### PowerShell Command Examples

```powershell
# 1. Inspect the governance lifecycle status and hashes of a report
python -m engine.governance_cli status --report-id "reason_20261108_052517_bae379e8"

# 2. Record substantive human review and approval
python -m engine.governance_cli review `
  --report-id "reason_20261108_052517_bae379e8" `
  --decision approved `
  --reviewer "Dr. S. Radhakrishnan" `
  --notes "Scholarly review confirms Niṣkāma Karma synthesis and valid comparative methodology."

# 3. Explicitly authorize a report for publication
python -m engine.governance_cli authorize `
  --report-id "reason_20261108_052517_bae379e8" `
  --authorizer "Editorial Board Director" `
  --channel "local_file" `
  --notes "Authorized for primary research publication and archive generation."

# 4. Publish the authorized report through the local file publisher
python -m engine.governance_cli publish `
  --report-id "reason_20261108_052517_bae379e8" `
  --channel "local_file"

# 5. Export published report to both JSON and publication-grade Markdown
python -m engine.governance_cli export `
  --report-id "reason_20261108_052517_bae379e8" `
  --format both `
  --output-dir outputs/publications

# 6. View the complete append-only audit trail for a governance record
python -m engine.governance_cli audit --report-id "reason_20261108_052517_bae379e8"
```

---

## 10. Real-Time Internet Intelligence (Part A) CLI & Workflow

### Overview & Security Mandate
The Real-Time Internet Intelligence engine searches the live internet, retrieves current information, classifies source credibility, detects semantic conflicts across results, and separates document publication dates from retrieval timestamps.

> **Security Mandate — Untrusted External Web Data:**
> All retrieved web content is treated strictly as **untrusted external data**, never as system instructions.
> - **Prompt Injection Defense:** Known jailbreak phrases (`Ignore previous instructions`, `SYSTEM PROMPT:`, etc.) are sanitized, system tags are defused, and content is wrapped in strict isolation tags.
> - **SSRF Protection:** `is_safe_url()` blocks loopback (`127.0.0.1`), private RFC1918 subnets, AWS/cloud metadata (`169.254.169.254`), and prohibited protocols.
> - **Robots.txt & Fair Use:** Respects `robots.txt` crawling directives via `RobotsPolicyChecker` and limits extracts to short research snippets.

### Credibility Tiers
1. `official`: Government portals (.gov, .gov.in, .mil) and international agencies (WHO, UN).
2. `academic`: Peer-reviewed journals and preprint servers (.edu, nature.com, arxiv.org, doi.org).
3. `credible_news`: Verified global journalistic institutions (Reuters, AP, BBC, The Hindu).
4. `general`: Open web sources with baseline credibility weighting (0.50).

### PowerShell Command Examples

```powershell
# 1. Execute deterministic offline search with MockSearchProvider
python -m engine.search_cli search "recent cognitive research on procrastination" --mock

# 2. Output full JSON envelope with credibility scores & hashes
python -m engine.search_cli search "quantum computing 2026" --mock --json

# 3. Safely fetch and sanitize a webpage (respecting SSRF and robots.txt)
python -m engine.search_cli fetch "https://en.wikipedia.org/wiki/Bhagavad_Gita"

# 4. Check whether robots.txt permits crawling a target URL
python -m engine.search_cli check-robots "https://nature.com/articles"
```

---

## 11. Unified Intelligence Engine & 12-Dimensional Response System

### Layer 1 Architecture Overview
The Unified Intelligence Engine integrates all six Layer 1 subsystems into a single, cohesive pair programming and research pipeline:
1. **Intelligent Subsystem Routing:** Selectively invokes traditional Gītā knowledge, empirical research, and live internet search instead of indiscriminately firing every subsystem.
2. **Anti-Hallucination Fact-Checking Gate:** Every output is deterministically validated before entering human review.
3. **Module 5 Human Governance:** Substantive human approval ($\ge 20$ chars) and cryptographic fingerprint protection (`approved_hash`).
4. **12-Dimensional Unified Response Schema:** Standardized machine-readable envelope.

```
[User Inquiry]
       │
       ▼
[Subsystem Selection Router: classify_subsystems()]
  ├── Traditional Knowledge (Gītā)? ──► [Knowledge Retrieval Bridge]
  ├── Empirical Scientific Research? ─► [Research Intelligence Layer]
  └── Real-Time Live Web Search? ────► [Real-Time Search Manager]
       │
       ▼
[Context Builder] (Sanitizes & Bounds Provenance)
       │
       ▼
[AI Reasoning Engine] (OpenAI / MockLLMProvider)
       │
       ▼
[Module 4 Fact-Checking Audit]
       │
  ┌────┴────────────────────────┐
  ▼                             ▼
[Passed Verified]     [Failed / Compromised]
  │                             │
  ▼                             ▼
Status: pending_review  Status: validation_failed (Approval Blocked)
  │
  ▼
[Module 5 Human Governance Review & Authorization]
  │
  ▼
[Publishing Pipeline: LocalFilePublisher] (JSON + Markdown)
```

### The 12 Dimensions of `UnifiedResponse`
1. `direct_answer`: Concise 2-3 sentence executive answer.
2. `detailed_explanation`: Deep comparative epistemological analysis.
3. `traditional_perspective`: Verified Gītā principles and verse citations.
4. `scientific_perspective`: Modern empirical and cognitive paradigms.
5. `current_developments`: Live web intelligence, recent studies, and publication dates.
6. `supporting_evidence`: Consolidated supporting findings across scripture, science, web.
7. `contradicting_evidence`: Conflicting findings, boundary conditions, and semantic disagreements.
8. `source_citations`: Explicit citations with URLs, publication dates, and retrieval timestamps.
9. `uncertainty_and_limitations`: Epistemic boundaries and identified research gaps.
10. `fact_checking_results`: Deterministic Module 4 anti-hallucination validation audit.
11. `human_review_status`: Reviewer identity, review notes, approval hash, and audit trail.
12. `report_id` and ISO 8601 UTC provenance timestamps.

### Running the Complete Layer 1 Pipeline

```powershell
# 1. Run full 12-dimensional unified response generation
python app.py "What does the Bhagavad Gita teach in Chapter 2, Verse 47 about action and procrastination?" --unified --mock-llm --mock-web

# 2. Run the full 135-test Layer 1 suite offline
python -m unittest discover -s tests -v

# 3. Run the 14 Part F integration tests
python -m unittest tests/test_unified_orchestrator.py -v
```

---

## 12. Separately Invoked Live Smoke Tests

ANTARĀ provides isolated live network and live OpenAI API smoke tests in `tests/test_live_smoke.py`. These tests are skipped by default during offline test discovery to preserve hermetic execution.

To execute live smoke tests on-demand in PowerShell:

```powershell
# 1. Enable live testing environment variable
$env:ANTARA_ENABLE_LIVE_TESTS = "1"

# 2. (Optional) Set your OpenAI API key for live LLM smoke test
$env:OPENAI_API_KEY = "sk-..."

# 3. Run the live smoke tests
python -m unittest tests/test_live_smoke.py -v
```

---

## 13. Controlled JSON Import Schema

The importer in `engine/knowledge.py` accepts UTF-8 JSON files in either of two formats:

### Format A: Batch Object with Shared Source
```json
{
  "source": {
    "title": "The Bhagavadgita: With an Introductory Essay, Sanskrit Text, English Translation and Notes",
    "author": "Dr. S. Radhakrishnan",
    "translator": "Dr. S. Radhakrishnan",
    "edition": "HarperCollins 1993",
    "year": 1993,
    "url": "https://example.org/radhakrishnan-gita",
    "rights_note": "Used for research commentary under scholarly fair dealing."
  },
  "verses": [
    {
      "chapter": 2,
      "verse": 47,
      "sanskrit": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।\nमा कर्मफलहेतुर्भूर्मा ते सङ्गोऽस्त्वकर्मणि॥",
      "transliteration": "karmaṇy evādhikāras te mā phaleṣu kadācana |\nmā karma-phala-hetur bhūr mā te saṅgo 'stv akarmaṇi ||",
      "translation": "To action alone hast thou a right and never at all to its fruits; let not the fruits of action be thy motive; neither let there be in thee any attachment to inaction.",
      "language": "en",
      "locator": "Chapter 2, Verse 47, p. 119",
      "notes": "Foundational verse defining Niṣkāma Karma (desireless action)."
    }
  ]
}
```

### Import Rules & Invariants:
1. **Source Text Exactness:** Punctuation, linebreaks, Devanagari characters, and IAST transliterations are preserved exactly without lossy stripping.
2. **Duplicate Protection:** Verses with identical `(source_id, chapter, verse)` are rejected or skipped during batch imports without aborting other valid rows.
3. **Partial Failure Isolation:** Invalid rows (e.g., chapter > 18, missing Sanskrit) are logged with row numbers while valid rows in the batch import successfully.
4. **Mandatory Initial Unreviewed State:** Every imported record enters the database with `verification_status: 'unreviewed'`.

---

## 14. Mechanical vs. Human Verification

| Dimension | Mechanical Verification (Application Level) | Human Verification (Scholarly & Domain Level) |
| :--- | :--- | :--- |
| **Primary Scope** | Syntactic validation, foreign key constraints, SHA-256 hashing. | Epistemological and philological authentication. |
| **Checks Enforced** | Chapters bounded (1–18), verses $\ge 1$, non-empty texts, cryptographic fingerprint matching. | Physical/critical edition collation (e.g., BORI, Nirnaya Sagar Press, Gita Press). |
| **Invalidation** | When textual content changes, status resets to `unreviewed` automatically. | Requires human reviewer identity, date, and substantive, verifiable evidence. |
| **Golden Rule** | **A computer check cannot determine theological or historical authenticity.** | **A URL alone is NEVER verification.** |

---

## 15. Next Implementation Layers (Layers 2–5 Roadmap)

1. **Layer 2 (Multilingual Knowledge & Ontology Expansion):** Expanded Sanskrit text corpus, commentary comparison engine (Shankara, Ramanuja, Madhva), and philosophical ontology mapping.
2. **Layer 3 (Multi-Channel Web & Social Distribution):** Substack, Medium, X/Twitter, and WordPress publisher adapters built on `PublishingProvider`.
3. **Layer 4 (Production Observability & SLA Monitoring):** Real-time metrics for claim verification, latency, human review SLAs, and security anomaly detection.
4. **Layer 5 (Decentralized Provenance & Trust):** Cryptographic attestation anchoring and distributed provenance graphs.


