# Tasks Document

- [ ] 1. Implement conversation workflow endpoints in `codegen_service.py`
  - File: `textmsa/services/codegen/codegen_service.py`
  - Add handlers for `conversations/start`, `conversations/{template_id}/continue`, and `conversations/{template_id}` using `CodegenAgent` + Mongo persistence.
  - Persist `CodegenConversation` with ordered `ConversationMessage` entries and enforce required fields (`service_id`, `user_requirement`, artifact metadata).
  - _Leverage: `textmsa/services/data/mongodb_models.py`, `textmsa/services/file/file_service.py`_
  - _Requirements: Requirement 1 (Conversation-Driven Template Authoring)_
  - _Prompt: Role: Python Backend Engineer experienced with FastAPI + MongoDB | Task: Implement conversation endpoints per Requirement 1, ensuring draft templates, conversation history, and validation errors flow through `CodegenService` | Restrictions: Keep persistence layer limited to Mongo collections already configured, avoid breaking existing template CRUD | Success: Conversations can start/continue, history is retrievable, invalid payloads return 4xx with descriptive detail._

- [ ] 2. Enforce template lifecycle transitions & status guards
  - File: `textmsa/services/codegen/codegen_service.py`
  - Add `confirm`, `generate-code`, `finalize` methods that check `CodegenStatus` order and update Mongo documents atomically.
  - Return structured errors (HTTP 409/400) when preconditions fail; include timestamps and metadata in responses.
  - _Leverage: `CodegenStatus`, `codegen_template_from_dict` helpers_
  - _Requirements: Requirement 2 (Template Lifecycle Enforcement)_
  - _Prompt: Role: Python Backend Engineer focused on workflow engines | Task: Wire status guards and mutation paths for template lifecycle, updating Mongo and filesystem artifacts | Restrictions: No raw Mongo updates without optimistic checks, reuse `_save_template_code` for file writes | Success: Templates cannot skip stages, lifecycle APIs respond with updated payloads and consistent error handling._

- [ ] 3. Build execution orchestration + polling APIs
  - File: `textmsa/services/codegen/codegen_service.py`, `codegen_executor.py`
  - Implement `POST /codegen/templates/{template_id}/execute`, `GET /codegen/executions`, `GET /codegen/executions/{execution_id}` including pagination, status filters, and log/output payloads.
  - Use `CodegenExecutor` thread pool jobs and persist `CodegenExecution` documents with polling-ready fields (status, logs, output references).
  - _Leverage: `ThreadPoolExecutor`, `CodegenExecutionStatus`, `file_manager`_
  - _Requirements: Requirement 3 (Execution Tracking & Context Scoping)_
  - _Prompt: Role: Python Backend Engineer with async job expertise | Task: Orchestrate execution requests, background processing, and history retrieval per Requirement 3 | Restrictions: Keep executor stateless, store large logs in filesystem when >1MB, no dependency on legacy execution tables | Success: Executions can be triggered, monitored, and filtered; backend enforces project/service scope._

- [ ] 4. Expand Mongo schema indexes + migrations for conversations/executions
  - File: `codegen_service.py` `_create_indexes`, migration scripts directory (if applicable)
  - Ensure compound indexes (template_id + user_id, status + created_at) exist for conversations/templates/executions to support frontend filters.
  - Provide simple migration notes or script to backfill new fields (e.g., `project_id`, `service_id`) for fresh deployments.
  - _Leverage: `pymongo ASCENDING/DESCENDING`, existing `_create_indexes` method_
  - _Requirements: Non-Functional Reliability + Requirement 3_
  - _Prompt: Role: Python Backend Engineer with MongoDB expertise | Task: Harden indexes supporting new workflows and document migration steps | Restrictions: No destructive migrations; ensure commands are idempotent | Success: Index creation succeeds on clean deploys, query plans stay performant._

- [ ] 5. File-service integration for artifact selection & execution outputs
  - File: `codegen_service.py`, `templates/` (if seed configs needed)
  - Reuse `file_service` to validate selected input artifacts during conversation start; attach `output_data` references to executions via `file_manager`.
  - Provide helper to scope available files by `service_id` so frontend lists only authorized artifacts.
  - _Leverage: `textmsa/services/file/file_service.py`, `file_manager` APIs_
  - _Requirements: Requirement 1, Requirement 3_
  - _Prompt: Role: Python Backend Engineer with storage integration experience | Task: Ensure file metadata and persisted outputs remain consistent with service/project scoping | Restrictions: Avoid direct filesystem paths in API responses; use IDs + descriptions | Success: Conversations/executions read/write files through shared services with proper scoping._

- [ ] 6. Validation & error-handling middleware
  - File: `codegen_service.py` (helper functions), shared utils (new module if needed)
  - Introduce reusable validators for `project_id/service_id` authorization, status transitions, and payload schemas to keep endpoints clean.
  - Standardize HTTPException usage with localized `detail/message`.
  - _Leverage: `fastapi.HTTPException`, global auth context_
  - _Requirements: Non-Functional Security & Usability_
  - _Prompt: Role: Python Backend Engineer specializing in API contracts | Task: Build validation helpers enforcing scope + status rules, feeding clear error messages to UI | Restrictions: Do not duplicate global interceptors; keep helpers pure for testability | Success: All new endpoints share consistent validation + error responses._

- [ ] 7. Automated tests (unit + integration)
  - Files: `tests/services/codegen/test_codegen_service.py`, `tests/services/codegen/test_executor.py`
  - Cover conversation flows, lifecycle guards, execution creation, and failure paths using fakes for LLM, Mongo, and file layers.
  - Add integration-style tests that spin up in-memory Mongo (or mock) to verify API contracts serialize as expected.
  - _Leverage: existing pytest fixtures, `mongomock` (if acceptable)_
  - _Requirements: All functional requirements_
  - _Prompt: Role: Python QA Engineer with pytest expertise | Task: Ensure high-coverage tests validating new workflows, including race conditions on lifecycle updates | Restrictions: Tests must run offline; avoid hitting real LLM/executor | Success: CI suite catches regressions, coverage includes happy paths + edge cases._

- [ ] 8. Observability & documentation updates
  - Files: `structure.md`, `README.md`, logging config
  - Add structured logs/metrics around conversation latency, execution duration, and failure causes; document new flows in README.
  - Mention instrumentation hooks in `structure.md` (observability section) and update requirements mapping.
  - _Leverage: `textmsa.logging_config`, future observability stubs_
  - _Requirements: Non-Functional Reliability + Documentation Standards_
  - _Prompt: Role: Python Backend Engineer with observability focus | Task: Wire logging/metrics for critical paths and keep docs aligned | Restrictions: Logging must remain GDPR-safe; no sensitive payloads | Success: Operators can trace template IDs through logs; docs describe how to monitor endpoints._
