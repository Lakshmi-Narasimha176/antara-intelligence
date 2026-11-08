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

## 5. Controlled JSON Import Schema

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

## 6. Mechanical vs. Human Verification

| Dimension | Mechanical Verification (Application Level) | Human Verification (Scholarly & Domain Level) |
| :--- | :--- | :--- |
| **Primary Scope** | Syntactic validation, foreign key constraints, SHA-256 hashing. | Epistemological and philological authentication. |
| **Checks Enforced** | Chapters bounded (1–18), verses $\ge 1$, non-empty texts, cryptographic fingerprint matching. | Physical/critical edition collation (e.g., BORI, Nirnaya Sagar Press, Gita Press). |
| **Invalidation** | When textual content changes, status resets to `unreviewed` automatically. | Requires human reviewer identity, date, and substantive, verifiable evidence. |
| **Golden Rule** | **A computer check cannot determine theological or historical authenticity.** | **A URL alone is NEVER verification.** |

---

## 7. Next Implementation Modules

1. **Research & Evidence Retrieval:** Structured external evidence gathering distinguishing empirical facts from hypotheses.
2. **Verification & Fact-Checking Engine:** Strict citation cross-referencing ensuring no AI hallucinations or fabricated claims.
3. **HITL Governance & Publishing Pipeline:** Cryptographic sign-off and publication approval state machine.


