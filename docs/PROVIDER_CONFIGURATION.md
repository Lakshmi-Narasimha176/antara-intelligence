# ANTARĀ — Provider and Configuration Guide

This document describes how to configure and operate inference and search providers in ANTARĀ Layer 1.

---

## 1. Local-First Operating Principle

ANTARĀ is built around a **local-first** operating model:
- **Default Inference**: Ollama local server (`http://localhost:11434`), configured model `qwen2.5:1.5b`.
- **No Mandatory Cloud API**: You do **not** need an OpenAI API key or any external credentials to develop, test, or run ANTARĀ.
- **Offline Reliability**: The entire Layer 1 test suite and core engine run completely offline using deterministic mocks or local providers.
- **No Silent Fallback**: If an explicit provider (e.g. `ollama`) is chosen and fails, ANTARĀ raises an explicit, actionable exception rather than silently calling a cloud provider.

---

## 2. Configuring Local Ollama

### Environment Variables
| Variable | Default Value | Description |
|---|---|---|
| `ANTARA_LLM_PROVIDER` | `mock` (or `ollama`) | Active provider (`mock`, `ollama`, or `openai`). |
| `ANTARA_OLLAMA_BASE_URL` | `http://localhost:11434` | Base HTTP endpoint for Ollama. |
| `ANTARA_OLLAMA_MODEL` | `qwen2.5:1.5b` | Model tag to use for generation. |
| `ANTARA_OLLAMA_TIMEOUT` | `120` | HTTP request timeout in seconds. |

### Verifying Ollama is Running
From PowerShell or Command Prompt:
```powershell
curl http://localhost:11434/api/tags
```
Or start the Ollama service:
```powershell
ollama serve
```

### Verifying and Installing Models
List installed models:
```powershell
ollama list
```
Pull the recommended lightweight model:
```powershell
ollama pull qwen2.5:1.5b
```
If you wish to use a different model (e.g., `llama3.2:1b` or `mistral:7b`), set:
```powershell
$env:ANTARA_OLLAMA_MODEL="llama3.2:1b"
```

### Handling Missing Models
If the configured model is not installed on Ollama, `OllamaProvider` raises `OllamaModelNotFoundError` with an explicit message:
```
Model '<model_name>' not found in Ollama. Install it with: ollama pull <model_name>
```
ANTARĀ will **never** automatically download gigabytes of model weights without user consent.

---

## 3. Offline & Testing Configuration

To run entirely offline with zero external network or local daemon requirements:
```powershell
$env:ANTARA_LLM_PROVIDER="mock"
```
Or leave `ANTARA_LLM_PROVIDER` unset; `UnifiedEngine` defaults safely to `MockLLMProvider` for testing when no environment overrides exist.

All unit and integration tests (except opt-in live smoke tests) use `MockLLMProvider` and `MockSearchProvider` to guarantee deterministic, offline execution.

---

## 4. Optional External Providers (OpenAI)

External providers are **strictly optional** and must be explicitly configured:
1. Set the provider choice:
   ```powershell
   $env:ANTARA_LLM_PROVIDER="openai"
   ```
2. Set your API key:
   ```powershell
   $env:OPENAI_API_KEY="sk-..."
   ```
If `OPENAI_API_KEY` is missing when `ANTARA_LLM_PROVIDER=openai`, an explicit `LLMConfigError` is raised immediately.

---

## 5. Live Internet Search Configuration

Web search is separate from model inference:
- By default, `UnifiedEngine` uses `MockSearchProvider` for offline safety.
- Optional search providers implement `SearchProvider` ABC (`engine.search`).
- Web page extraction strictly adheres to:
  - Private IP & loopback SSRF prohibitions.
  - Target domain `robots.txt` disallow policies.
  - In-memory bounded LRU query cache (100 items, 3600s TTL).
  - Rate limiting (max 10 queries per minute per domain).
