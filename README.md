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

# 3. Run the full 90-test suite covering all modules & the retrieval bridge
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

## 9. Controlled JSON Import Schema

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

## 10. Mechanical vs. Human Verification

| Dimension | Mechanical Verification (Application Level) | Human Verification (Scholarly & Domain Level) |
| :--- | :--- | :--- |
| **Primary Scope** | Syntactic validation, foreign key constraints, SHA-256 hashing. | Epistemological and philological authentication. |
| **Checks Enforced** | Chapters bounded (1–18), verses $\ge 1$, non-empty texts, cryptographic fingerprint matching. | Physical/critical edition collation (e.g., BORI, Nirnaya Sagar Press, Gita Press). |
| **Invalidation** | When textual content changes, status resets to `unreviewed` automatically. | Requires human reviewer identity, date, and substantive, verifiable evidence. |
| **Golden Rule** | **A computer check cannot determine theological or historical authenticity.** | **A URL alone is NEVER verification.** |

---

## 11. Next Implementation Modules

1. **Module 5: HITL Governance & Publishing Pipeline:** Multi-stage human approval state machine, cryptographic publication sign-off, and verified publication generation.


