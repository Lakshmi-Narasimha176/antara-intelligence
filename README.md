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

## 3. Current Architecture & State

### Components Audited
- **Entry Point:** `app.py` - CLI argument parsing, console UTF-8 stream configuration, brief generation, and disk persistence to `outputs/latest_brief.json`.
- **Orchestrator:** `engine/orchestrator.py` - Question validation, character limit bounds, topic classification heuristics, and dataclass instantiation.
- **Test Suite:** `tests/test_orchestrator.py` - Unit test coverage for input normalization, empty/type validation, boundary testing, classification heuristics, and brief generation.
- **Outputs:** `outputs/latest_brief.json` - Timestamped, human-supervised research brief artifact.

---

## 4. Next Implementation Modules

1. **Source-Traceable Knowledge Base:** Bhagavad Gita verses, accredited translations, word-by-word meanings, and scholarly commentary with immutable citations.
2. **Research & Evidence Retrieval:** Structured evidence gathering with clear separation of facts, hypotheses, and interpretations.
3. **Verification & Fact-Checking Engine:** Anti-hallucination cross-checker to validate citations before human presentation.
4. **Human Review & Approval Workflow:** Mandatory human sign-off gating mechanism.

