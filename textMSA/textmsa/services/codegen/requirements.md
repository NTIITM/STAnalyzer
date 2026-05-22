# Requirements Document

## Introduction

We need a cohesive backend contract that lets the frontend Codegen Workspace drive multi-turn template generation, lifecycle transitions, and execution history without manual intervention. This document enumerates the backend-facing expectations so engineers can verify that `/codegen` endpoints expose the metadata, status transitions, and error semantics the UI relies upon to deliver an end-to-end experience for analysts iterating on spatial transcriptomics workflows.

## Alignment with Product Vision

The code generation workspace is intended to let life-science analysts describe what they need, iterate with an AI assistant, and operationalize the resulting scripts within governed projects and services. Completing the backend feature set (conversation APIs, lifecycle hooks, execution visibility) keeps the product promise of “describe → generate → inspect → finalize” entirely inside TextMSA, eliminating context switches and ensuring compliance with project/service scopes defined in `product.md`.

## Requirements

### Requirement 1 – Conversation-Driven Template Authoring

**User Story:** As a bioinformatics analyst, I want to start and continue guided conversations tied to a project/service, so that I can iteratively shape templates before confirming them.

#### Acceptance Criteria

1. WHEN the frontend calls `POST /codegen/conversations/start` with `user_requirement`, `service_id`, project context, and selected artifacts THEN the backend SHALL create (or reuse) a draft template, return `template_id`, `conversation_id`, and the agent’s first message.
2. IF the template is still in a draftable status (`template_generated`) THEN the backend SHALL accept `POST /codegen/conversations/{templateId}/continue` messages, append them to history, and respond with the updated template payload plus the assistant turn.
3. WHEN the UI queries `GET /codegen/conversations/{templateId}` THEN the backend SHALL return an ordered message list (role, text, timestamp, requires_action) so the client can render the full timeline.
4. IF required fields (service_id, user_requirement, artifact selection) are missing THEN the backend SHALL return a 400 with a descriptive `message` or `detail` the UI can display inline.

### Requirement 2 – Template Lifecycle Enforcement

**User Story:** As a service maintainer, I want lifecycle endpoints to enforce state transitions, so that templates cannot skip confirmation or code generation gates.

#### Acceptance Criteria

1. WHEN a template is confirmed via `POST /codegen/templates/{templateId}/confirm` THEN the backend SHALL validate status `template_generated`, update status to `template_confirmed`, and return the full template payload.
2. WHEN the user requests `POST /codegen/templates/{templateId}/generate-code` THEN the backend SHALL require status `template_confirmed`, produce `generated_code`, transition status to `code_generated`, and return updated metadata (parameter schema, timestamps).
3. IF `POST /codegen/templates/{templateId}/finalize` is called before a successful execution is recorded THEN the backend SHALL reject the request with a non-2xx `code` explaining the missing prerequisite.
4. WHEN the frontend issues `PUT /codegen/templates/{templateId}` for editable fields THEN the backend SHALL allow updates only while status is `template_generated` or review equivalent, otherwise respond with a 409-style error to prevent stale edits.

### Requirement 3 – Execution Tracking & Context Scoping

**User Story:** As an analyst, I want executions tied to a template/project/service with logs and outputs, so that I can monitor runs without leaving the workspace.

#### Acceptance Criteria

1. WHEN `POST /codegen/templates/{templateId}/execute` is triggered with validated parameters THEN the backend SHALL create an execution bound to the same `project_id`/`service_id`, return `execution_id`, initial status, and timestamps.
2. WHEN `GET /codegen/executions` is called with `template_id` (plus optional project/service filters) THEN the backend SHALL return executions sorted newest-first along with `total` for pagination.
3. WHEN `GET /codegen/executions/{executionId}` is fetched THEN the backend SHALL include status, error_message, execution_log (truncatable), and output artifact references so the UI can surface logs and downloads.
4. IF the request lacks the correct project/service scope or user permissions THEN the backend SHALL respond with 401/403 using `detail` or `message` so the global interceptor can redirect or show errors.

## Non-Functional Requirements

### Code Architecture and Modularity
- **Single Responsibility Principle**: Route handlers for conversations, templates, and executions must stay isolated so each file exposes one resource contract.
- **Modular Design**: Shared validation (project/service scoping, status guards) should live in reusable helpers to keep logic consistent across endpoints.
- **Dependency Management**: Conversation flows should not directly import execution modules—use service interfaces to keep cross-feature dependencies explicit.
- **Clear Interfaces**: Define TypeScript/JSON schemas for template and execution payloads so both frontend and backend share the same contracts via `src/types/codegen.ts`.

### Performance
- List endpoints (`/codegen/templates`, `/codegen/executions`) should return within 500 ms for the first 100 items and support pagination via `skip/limit`.
- Conversation start/continue should stream or respond within 3 s; if generation takes longer, use async task IDs so the UI can poll without blocking.

### Security
- Enforce `Authorization` bearer checks and verify that `user_id` has access to the requested `project_id/service_id`.
- Sanitize conversation messages to avoid command injection before passing them to LLM providers or execution backends.
- Ensure execution artifacts are stored with per-project ACLs; signed URLs must expire within a configurable window.

### Reliability
- All lifecycle transitions must be atomic; use transactions or optimistic locking to avoid double confirmations.
- Provide idempotency for conversation start (based on draft hash or client token) to prevent duplicate templates when the UI retries.
- Emit structured logs when transitions fail so observability dashboards can correlate template_id with execution issues.

### Usability
- Error payloads should include actionable `message/detail` strings in Chinese or English depending on `Accept-Language` so the UI can render friendly toasts.
- Include human-readable timestamps (ISO 8601) and status enums so the frontend can present badges without extra mapping.
