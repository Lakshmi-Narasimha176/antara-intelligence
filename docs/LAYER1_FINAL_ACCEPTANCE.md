# ANTARĀ Layer 1 Final Acceptance and Traceability

## Acceptance result

The requested regression suite passed with **192 passed, 0 failed, and 3 skipped**.
The three skips are opt-in live network/API smoke tests. This result verifies the
regression suite; it does not, by itself, establish that every original DPR acceptance
category is evidenced.

### Summary arithmetic

| Classification | Count |
|---|---:|
| VERIFIED | 20 |
| PARTIALLY VERIFIED | 10 |
| NOT VERIFIED | 3 |
| NOT APPLICABLE | 1 |
| **Total categories** | **34** |

| Verification command | Result |
|---|---|
| `.\.venv\Scripts\python.exe -m compileall -q engine tests` | Passed |
| `.\.venv\Scripts\python.exe -m pytest --collect-only -q` | 195 collected |
| `.\.venv\Scripts\python.exe -m pytest -v` | 192 passed, 0 failed, 3 skipped |
| `git diff --check` | Passed |

## Original 34-category DPR evidence matrix

The statuses below apply only to the original mandatory DPR categories. A mocked or
offline test directly verifies only the behavior it exercises; where actual external
service behavior remains untested, the status is PARTIALLY VERIFIED. Test names are
shown verbatim, with evidence type and file. “No direct test found” is an evidence gap,
not a passing result.

| # | Original DPR category | Classification | Evidence type and actual test evidence |
|---:|---|---|---|
| 1 | Traditional knowledge only | VERIFIED | Integration test with local SQLite knowledge and mocked search: `test_01_traditional_knowledge_only_question` — [tests/test_unified_orchestrator.py](../tests/test_unified_orchestrator.py). |
| 2 | Live information only | PARTIALLY VERIFIED | Integration test with mock search: `test_02_live_information_question` — [tests/test_unified_orchestrator.py](../tests/test_unified_orchestrator.py). Opt-in live checks `test_live_network_connectivity` and `test_live_robots_txt_and_page_fetch` — [tests/test_live_smoke.py](../tests/test_live_smoke.py) — were skipped. |
| 3 | Scientific research only | PARTIALLY VERIFIED | Integration test against seeded local research records: `test_03_scientific_research_question` — [tests/test_unified_orchestrator.py](../tests/test_unified_orchestrator.py). Live external research-provider behavior is not established by this mocked/local fixture. |
| 4 | External model reasoning only | PARTIALLY VERIFIED | Mocked provider test: `test_openai_response_normalization_with_injected_client` — [tests/test_reasoning.py](../tests/test_reasoning.py). Live test `test_live_openai_api_completion` — [tests/test_live_smoke.py](../tests/test_live_smoke.py) — was skipped. |
| 5 | Mixed knowledge | PARTIALLY VERIFIED | Integration tests with local knowledge/research and mock search: `test_04_hybrid_traditional_and_modern_knowledge` and `test_05_hybrid_stored_knowledge_and_current_internet` — [tests/test_unified_orchestrator.py](../tests/test_unified_orchestrator.py). Live external retrieval remains untested. |
| 6 | Missing provider | VERIFIED | Integration test: `test_06_missing_live_search_provider_handling` — [tests/test_unified_orchestrator.py](../tests/test_unified_orchestrator.py). |
| 7 | Missing configuration | VERIFIED | Integration and provider unit tests: `test_08_missing_api_configuration_fallback` — [tests/test_unified_orchestrator.py](../tests/test_unified_orchestrator.py); `test_openai_provider_config_validation` — [tests/test_reasoning.py](../tests/test_reasoning.py); `test_openai_web_search_without_api_key_discloses_cleanly` — [tests/test_search.py](../tests/test_search.py). |
| 8 | Invalid credentials | NOT VERIFIED | No direct invalid-credential rejection/redaction test found. `test_openai_provider_config_validation` in [tests/test_reasoning.py](../tests/test_reasoning.py) tests a missing key and invalid settings, not rejected credentials; the live OpenAI test was skipped. |
| 9 | Provider failure | PARTIALLY VERIFIED | Mocked integration tests: `test_07_search_provider_failure_resilience` — [tests/test_unified_orchestrator.py](../tests/test_unified_orchestrator.py); `test_mock_provider_failure_modes` — [tests/test_reasoning.py](../tests/test_reasoning.py). Real external provider failure behavior remains untested. |
| 10 | Timeout | PARTIALLY VERIFIED | Mocked unit/integration tests: `test_generate_timeout` — [tests/test_ollama_provider.py](../tests/test_ollama_provider.py); `test_search_manager_handles_timeout_with_clear_disclosure` — [tests/test_search.py](../tests/test_search.py); `test_handles_provider_timeout_and_network_failures` — [tests/test_research.py](../tests/test_research.py). Live timeout behavior was not exercised. |
| 11 | Retry exhaustion | VERIFIED | Unit test using an injected HTTP mock transport: `test_openai_retry_exhaustion_respects_limit_and_reports_final_error` — [tests/test_reasoning.py](../tests/test_reasoning.py). It asserts attempt count equals configured retries + 1 for limits 0, 1, and 2, and checks the final translated error. |
| 12 | Unsupported claims | VERIFIED | Integration and validator tests: `test_09_unsupported_claims_caught_by_validation` — [tests/test_unified_orchestrator.py](../tests/test_unified_orchestrator.py); `test_unsupported_research_claims` — [tests/test_fact_checker.py](../tests/test_fact_checker.py). |
| 13 | Invalid citations | VERIFIED | Integration and validator tests: `test_10_invalid_citations_caught_by_validation` — [tests/test_unified_orchestrator.py](../tests/test_unified_orchestrator.py); `test_valid_gita_source_reference` — [tests/test_fact_checker.py](../tests/test_fact_checker.py). |
| 14 | Contradictory sources | VERIFIED | Integration and unit tests: `test_11_contradictory_sources_detected` — [tests/test_unified_orchestrator.py](../tests/test_unified_orchestrator.py); `test_detect_conflicts_semantic_opposition` — [tests/test_search.py](../tests/test_search.py). |
| 15 | Stale information | VERIFIED | Unit tests: `test_stale_web_source_is_disclosed_as_historical` and `test_unknown_web_source_date_is_not_treated_as_current` — [tests/test_reasoning.py](../tests/test_reasoning.py). |
| 16 | Duplicate information | VERIFIED | Unit test: `test_deduplicate_results_removes_exact_and_near_duplicates` — [tests/test_search.py](../tests/test_search.py). |
| 17 | Malicious retrieved content | VERIFIED | Unit tests: `test_malicious_web_content_is_sanitized_and_isolated_from_system_instructions` — [tests/test_reasoning.py](../tests/test_reasoning.py); `test_prompt_injection_sanitization` — [tests/test_search.py](../tests/test_search.py). |
| 18 | Prompt injection | VERIFIED | Unit test: `test_prompt_injection_sanitization` — [tests/test_search.py](../tests/test_search.py). The reasoning isolation assertion is also covered by `test_malicious_web_content_is_sanitized_and_isolated_from_system_instructions` — [tests/test_reasoning.py](../tests/test_reasoning.py). |
| 19 | Unauthorized publishing | VERIFIED | Integration test: `test_13_publishing_without_authorization_is_blocked` — [tests/test_unified_orchestrator.py](../tests/test_unified_orchestrator.py); governance unit test `test_publishing_without_approval_is_blocked` — [tests/test_governance.py](../tests/test_governance.py). |
| 20 | Approval invalidation after edits | VERIFIED | Governance unit test: `test_content_modification_after_approval_invalidates_approval` — [tests/test_governance.py](../tests/test_governance.py). |
| 21 | Exact-content approval | VERIFIED | Governance unit tests: `test_exact_approved_content_fingerprint_gates_publication`, `test_fingerprint_mismatch_blocks_publication`, and `test_stored_content_tampering_after_authorization_blocks_publish` — [tests/test_governance.py](../tests/test_governance.py). |
| 22 | Concurrent requests | PARTIALLY VERIFIED | Deterministically synchronized governance concurrency test: `test_concurrent_authorization_allows_only_one_transition` — [tests/test_governance.py](../tests/test_governance.py). It verifies a single authorization race, not general simultaneous request behavior across the engine or all shared resources. |
| 23 | Database transaction safety | NOT VERIFIED | No direct rollback/atomicity test found. `test_dry_run_does_not_commit_records` — [tests/test_knowledge.py](../tests/test_knowledge.py) — verifies dry-run behavior only and is not sufficient evidence for database transaction safety. |
| 24 | Cache correctness | VERIFIED | Unit test: `test_search_manager_caching` — [tests/test_search.py](../tests/test_search.py). It verifies repeated identical queries return the cached response. |
| 25 | Offline operation | VERIFIED | Offline integration/unit tests: `test_mock_providers_and_unified_pipeline_run_without_network`, `test_ollama_failure_never_falls_back_to_cloud`, `test_missing_local_model_is_not_downloaded_automatically`, and `test_unavailable_network_search_reports_unavailable_without_credentials` — [tests/test_offline_mode.py](../tests/test_offline_mode.py). They deny outbound network calls for the mock pipeline, use a mocked local Ollama response, verify no cloud fallback or model download, and check graceful unavailable-search disclosure. |
| 26 | Poor network | PARTIALLY VERIFIED | Mocked failure tests: `test_search_manager_handles_timeout_with_clear_disclosure` and `test_search_manager_handles_rate_limits` — [tests/test_search.py](../tests/test_search.py); `test_handles_provider_timeout_and_network_failures` — [tests/test_research.py](../tests/test_research.py). No live degraded-network test was run. |
| 27 | Telugu | VERIFIED | Unit tests: `test_pure_telugu_language_identification` and `test_unswitched_telugu_metadata` — [tests/test_nlp_foundations.py](../tests/test_nlp_foundations.py). |
| 28 | English | VERIFIED | Unit tests: `test_pure_english_language_identification` and `test_unswitched_english_metadata` — [tests/test_nlp_foundations.py](../tests/test_nlp_foundations.py). |
| 29 | Telugu-English mixed | VERIFIED | Unit tests: `test_telugu_english_mixed_code_switched` and `test_code_switching_detection` — [tests/test_nlp_foundations.py](../tests/test_nlp_foundations.py). |
| 30 | End-to-end orchestration | PARTIALLY VERIFIED | Integration test using deterministic mock providers and local data: `test_14_complete_end_to_end_question_processing` — [tests/test_unified_orchestrator.py](../tests/test_unified_orchestrator.py). End-to-end operation with live external providers was not tested. |
| 31 | Backward compatibility | VERIFIED | Unit/integration tests: `test_backward_compatibility_with_standard_brief_creation` — [tests/test_retrieval.py](../tests/test_retrieval.py); `test_existing_module1_and_module2_compatibility` — [tests/test_research.py](../tests/test_research.py). |
| 32 | Configuration migration | NOT APPLICABLE | Configuration is environment-variable based, documented in [docs/PROVIDER_CONFIGURATION.md](PROVIDER_CONFIGURATION.md) and `.env.example`; no versioned configuration file or persisted configuration schema exists to migrate. The documented strategy is to evolve named environment variables compatibly, validate them at startup/use, and document changes; therefore no old-to-new migration mechanism or migration test is applicable. |
| 33 | Security and secret redaction | NOT VERIFIED | No direct secret-redaction test found. `test_prompt_injection_sanitization` — [tests/test_search.py](../tests/test_search.py) — covers untrusted-content sanitization, not secret redaction; `test_ssrf_prohibited_ips` in the same file tests URL safety, not credential exposure. |
| 34 | Resource and timeout limits | PARTIALLY VERIFIED | Unit tests cover input-length rejection and timeout handling: `test_rejects_question_too_long` — [tests/test_orchestrator.py](../tests/test_orchestrator.py); `test_generate_timeout` — [tests/test_ollama_provider.py](../tests/test_ollama_provider.py). Comprehensive resource-limit coverage (including response/page-size or concurrent-resource bounds) was not established. |

### Nine foundation areas

| # | Foundation area | Classification | Test evidence |
|---:|---|---|---|
| 1 | Orchestration and research-brief foundation | VERIFIED | `test_normalizes_whitespace`, `test_rejects_empty_question`, `test_classifies_philosophy`, `test_creates_human_supervised_brief` — [tests/test_orchestrator.py](../tests/test_orchestrator.py). |
| 2 | Traditional knowledge repository foundation | VERIFIED | `test_initializes_schema_and_enforces_foreign_keys`, `test_imports_valid_batch_and_preserves_unicode_exactness`, `test_tampering_detection_and_verified_only_exclusion` — [tests/test_knowledge.py](../tests/test_knowledge.py). |
| 3 | Knowledge retrieval bridge foundation | VERIFIED | `test_retrieves_verified_verse_by_chapter_and_verse`, `test_excludes_tampered_records_via_defense_in_depth`, `test_backward_compatibility_with_standard_brief_creation` — [tests/test_retrieval.py](../tests/test_retrieval.py). |
| 4 | Empirical research intelligence foundation | VERIFIED | `test_supporting_evidence_classification`, `test_contradicting_evidence_classification`, `test_handles_provider_timeout_and_network_failures`, `test_existing_module1_and_module2_compatibility` — [tests/test_research.py](../tests/test_research.py). |
| 5 | Anti-hallucination and fact-checking foundation | VERIFIED | `test_exact_quotation_matching`, `test_missing_source_references`, `test_contradicting_evidence_detection`, `test_database_failures` — [tests/test_fact_checker.py](../tests/test_fact_checker.py). |
| 6 | AI reasoning and provider foundation | VERIFIED | `test_end_to_end_reasoning_synthesis_success`, `test_mock_provider_failure_modes`, `test_openai_retry_exhaustion_respects_limit_and_reports_final_error` — [tests/test_reasoning.py](../tests/test_reasoning.py). |
| 7 | Human governance and publishing foundation | VERIFIED | `test_valid_state_transitions_lifecycle`, `test_exact_approved_content_fingerprint_gates_publication`, `test_concurrent_authorization_allows_only_one_transition`, `test_audit_history_is_append_only` — [tests/test_governance.py](../tests/test_governance.py). |
| 8 | Real-time internet intelligence foundation | PARTIALLY VERIFIED | `test_mock_search_provider_returns_structured_results`, `test_search_manager_handles_timeout_with_clear_disclosure`, `test_fetch_page_blocks_prohibited_ip`, `test_fetch_page_respects_robots_disallow` — [tests/test_search.py](../tests/test_search.py). Unmocked connectivity remains opt-in: `test_live_network_connectivity` and `test_live_robots_txt_and_page_fetch` — [tests/test_live_smoke.py](../tests/test_live_smoke.py), skipped in offline verification. |
| 9 | Unified engine and 12-dimensional response foundation | VERIFIED | `test_14_complete_end_to_end_question_processing` — [tests/test_unified_orchestrator.py](../tests/test_unified_orchestrator.py); `test_unified_response_surfaces_language_metadata` — [tests/test_nlp_foundations.py](../tests/test_nlp_foundations.py); stale-source disclosure assertions — [tests/test_reasoning.py](../tests/test_reasoning.py). |

### Fifteen capability groups

| # | Capability group | Classification | Test evidence |
|---:|---|---|---|
| 10 | Input validation and subsystem routing | VERIFIED | `test_rejects_non_string`, `test_rejects_question_too_long`, `test_classifies_behavior`, `test_falls_back_to_general` — [tests/test_orchestrator.py](../tests/test_orchestrator.py). |
| 11 | Knowledge persistence, constraints, and controlled import | VERIFIED | `test_rejects_invalid_chapter_bounds`, `test_rejects_duplicate_verse_under_same_source`, `test_dry_run_does_not_commit_records`, `test_handles_duplicates_and_partial_failures_gracefully` — [tests/test_knowledge.py](../tests/test_knowledge.py). |
| 12 | Verified retrieval and provenance preservation | VERIFIED | `test_excludes_unreviewed_records`, `test_excludes_rejected_records`, `test_excludes_modified_and_invalidated_records`, `test_create_brief_attaches_verified_knowledge` — [tests/test_retrieval.py](../tests/test_retrieval.py). |
| 13 | Research providers and evidence classification | VERIFIED | `test_contextual_evidence_classification`, `test_inconclusive_evidence_classification`, `test_collect_research_for_question` — [tests/test_research.py](../tests/test_research.py). This verifies the Layer 1 provider contract and mock behavior, not an unimplemented live adapter. |
| 14 | Deterministic claim and citation validation | VERIFIED | `test_valid_gita_source_reference`, `test_incorrect_quotations`, `test_unsupported_research_claims`, `test_validation_report_generation` — [tests/test_fact_checker.py](../tests/test_fact_checker.py). |
| 15 | Reasoning context construction and synthesis | VERIFIED | `test_context_includes_only_verified_verses_and_approved_evidence`, `test_end_to_end_reasoning_synthesis_success`, `test_unsupported_claim_fails_validation_and_blocks_approval` — [tests/test_reasoning.py](../tests/test_reasoning.py). |
| 16 | Provider contracts, deterministic mocks, optional OpenAI, and retries | VERIFIED | `test_mock_provider_defaults`, `test_mock_provider_failure_modes`, `test_openai_provider_config_validation`, `test_openai_response_normalization_with_injected_client`, `test_openai_retry_exhaustion_respects_limit_and_reports_final_error` — [tests/test_reasoning.py](../tests/test_reasoning.py). OpenAI remains optional; no API credential is used by these tests. |
| 17 | Local Ollama inference and offline-first execution | VERIFIED | `test_generate_success`, `test_generate_timeout`, `test_missing_local_model_is_not_downloaded_automatically`, `test_mock_providers_and_unified_pipeline_run_without_network`, `test_ollama_failure_never_falls_back_to_cloud` — [tests/test_ollama_provider.py](../tests/test_ollama_provider.py) and [tests/test_offline_mode.py](../tests/test_offline_mode.py). |
| 18 | Search provider abstraction, caching, and resilience | PARTIALLY VERIFIED | `test_mock_search_provider_returns_structured_results`, `test_search_manager_caching`, `test_search_manager_handles_timeout_with_clear_disclosure`, `test_search_manager_handles_rate_limits`, `test_stale_web_source_is_disclosed_as_historical`, `test_unknown_web_source_date_is_not_treated_as_current` — [tests/test_search.py](../tests/test_search.py) and [tests/test_reasoning.py](../tests/test_reasoning.py). External live service behavior remains opt-in and was skipped. |
| 19 | SSRF, robots policy, and page-fetch safety | VERIFIED | `test_ssrf_prohibited_ips`, `test_fetch_page_blocks_prohibited_ip`, `test_fetch_page_respects_robots_disallow` — [tests/test_search.py](../tests/test_search.py). |
| 20 | Malicious external payload sanitization and isolation | VERIFIED | `test_prompt_injection_sanitization` — [tests/test_search.py](../tests/test_search.py); `test_malicious_web_content_is_sanitized_and_isolated_from_system_instructions` — [tests/test_reasoning.py](../tests/test_reasoning.py). |
| 21 | Unified engine and response/evidence contracts | VERIFIED | `test_14_complete_end_to_end_question_processing` — [tests/test_unified_orchestrator.py](../tests/test_unified_orchestrator.py); `test_unified_response_surfaces_language_metadata` — [tests/test_nlp_foundations.py](../tests/test_nlp_foundations.py). Freshness fields are additive within current-development source records; the 12 top-level response dimensions remain unchanged. |
| 22 | Governance lifecycle, review, audit, and concurrent transitions | VERIFIED | `test_valid_state_transitions_lifecycle`, `test_audit_history_is_append_only`, `test_concurrent_authorization_allows_only_one_transition` — [tests/test_governance.py](../tests/test_governance.py). |
| 23 | Exact-content approval and publishing safeguards | VERIFIED | `test_exact_approved_content_fingerprint_gates_publication`, `test_stored_content_tampering_after_authorization_blocks_publish`, `test_content_modification_after_approval_invalidates_approval`, `test_fingerprint_mismatch_blocks_publication` — [tests/test_governance.py](../tests/test_governance.py). |
| 24 | Configuration versioning and migration policy | NOT APPLICABLE | No versioned configuration artifact or persisted configuration schema exists. Policy: [docs/PROVIDER_CONFIGURATION.md](PROVIDER_CONFIGURATION.md), §4. Runtime configuration test: `test_openai_provider_config_validation` — [tests/test_reasoning.py](../tests/test_reasoning.py). No migration system was introduced. |

### Ten NLP foundations

| # | NLP foundation | Classification | Test evidence |
|---:|---|---|---|
| 25 | Language identification | VERIFIED | `test_pure_telugu_language_identification`, `test_pure_english_language_identification`, `test_romanized_telugu_is_not_assumed_english`, `test_telugu_english_mixed_code_switched` — [tests/test_nlp_foundations.py](../tests/test_nlp_foundations.py). |
| 26 | Language metadata propagation | VERIFIED | `test_extract_language_metadata_helper`, `test_create_brief_propagates_nlp_metadata`, `test_unified_response_surfaces_language_metadata` — [tests/test_nlp_foundations.py](../tests/test_nlp_foundations.py). |
| 27 | Intent-detection interfaces | VERIFIED | `test_detects_philosophical_intent`, `test_detects_scientific_intent`, `test_detects_comparative_intent`, `test_detects_live_information_intent` — [tests/test_nlp_foundations.py](../tests/test_nlp_foundations.py). |
| 28 | Query-normalization interfaces | VERIFIED | `test_preserves_telugu_unicode_without_destructive_transforms`, `test_normalizes_whitespace_in_english` — [tests/test_nlp_foundations.py](../tests/test_nlp_foundations.py). |
| 29 | Semantic-retrieval interfaces | VERIFIED | `test_retrieves_candidates_above_threshold`, `test_threshold_filters_low_confidence` — [tests/test_nlp_foundations.py](../tests/test_nlp_foundations.py). |
| 30 | Entity and relation extraction | VERIFIED | `test_extracts_known_entities`, `test_extracts_relationships` — [tests/test_nlp_foundations.py](../tests/test_nlp_foundations.py). |
| 31 | Telugu-English code-switching | VERIFIED | `test_code_switching_detection`, `test_unswitched_english_metadata`, `test_unswitched_telugu_metadata` — [tests/test_nlp_foundations.py](../tests/test_nlp_foundations.py). |
| 32 | Language-aware provider selection | VERIFIED | `test_selects_direct_telugu_provider_without_forced_translation`, `test_selects_english_provider` — [tests/test_nlp_foundations.py](../tests/test_nlp_foundations.py). |
| 33 | NLP provider abstraction | VERIFIED | `test_default_nlp_provider`, `test_mock_nlp_provider` — [tests/test_nlp_foundations.py](../tests/test_nlp_foundations.py). |
| 34 | NLP evaluation interfaces | VERIFIED | `test_standard_evaluator_measures_accuracy_and_latency` — [tests/test_nlp_foundations.py](../tests/test_nlp_foundations.py). |

## Configuration and scope freeze

Layer 1 configuration remains environment-variable based, with local Ollama as the
optional local inference runtime and deterministic mock providers as the no-network
default. No cloud fallback or automatic model download is permitted. OpenAI remains
explicitly opt-in and no OpenAI API key is required.

No Layer 2 work or broad Layer 1 redesign is included in this acceptance.

## DPR acceptance disposition

The original DPR acceptance criteria are **not fully evidenced**. The matrix contains
20 VERIFIED, 10 PARTIALLY VERIFIED, 3 NOT VERIFIED, and 1 NOT APPLICABLE category
(34 total). Remaining evidence blockers are:

- Invalid credentials: no direct rejected-credential test.
- Database transaction safety: no direct transaction rollback/atomicity test.
- Security and secret redaction: no direct secret-redaction test.
- Live external retrieval/model behavior: opt-in live tests were skipped; related
  capability rows remain PARTIALLY VERIFIED.
- Concurrent requests and resource limits: only the specific authorization race and
  selected input/timeout bounds are covered, not the full category scope.
