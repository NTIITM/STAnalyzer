# Project Structure

## Directory Organization

```
textmsa/services/codegen/
├── __init__.py              # Export service factory helpers
├── README.md                # High-level service overview
├── requirements.md          # Backend requirements/acceptance criteria
├── structure.md             # (This doc) structure & conventions
├── codegen_service.py       # Orchestrates conversations, lifecycle, executions
├── codegen_agent.py         # LLM-facing agent that builds templates/schema
├── codegen_executor.py      # Multi-language execution sandbox
└── templates/               # Seed prompt or reusable code snippets (future-ready)
```

Supporting dependencies live in neighboring packages:
- `textmsa/services/data/mongodb_models.py` holds Pydantic-style models used across service, agent, executor.
- `textmsa/services/file/{file_service,file_manager}.py` supplies file metadata and storage paths.
- `textmsa/utils/llm.py` provides the LLM client abstraction consumed by `CodegenAgent`.

The service assumes MongoDB + filesystem storage configured via `textmsa.settings`.

## Naming Conventions

### Files
- **Core modules**: snake_case suffixed by responsibility (`codegen_service.py`, `codegen_agent.py`).
- **Support packages**: keep directory names singular nouns (`templates`, `fixtures` when added).
- **Executable scripts**: prefer verb-driven snake_case (`rebuild_index.py`) if introduced later.
- **Tests**: mirror module name with `_test.py` or `_spec.py` under `tests/services/codegen/`.

### Code
- **Classes/Types**: PascalCase (`CodegenService`, `CodegenExecutor`, `ConversationMessage`).
- **Functions/Methods**: snake_case verbs (`generate_template`, `_prepare_environment`).
- **Constants/Enums**: UPPER_SNAKE_CASE or Enum members in PascalCase (`ISO_FORMAT`, `CodegenStatus.TEMPLATE_GENERATED`).
- **Variables**: snake_case; reserve short names for local iterators only.

## Import Patterns

### Import Order
1. Python stdlib (`os`, `uuid`, `pathlib`, `datetime`).
2. Third-party libraries (`pymongo`, `fastapi`).
3. Internal absolute modules (`textmsa.logging_config`, `textmsa.services.data.mongodb_models`).
4. Local relative imports (currently none; keep it that way to aid refactors).

### Module/Package Organization
```
- Always use absolute imports rooted at `textmsa` to avoid circular references.
- Group domain models in `textmsa.services.data` so both API and worker layers share schemas.
- Keep LLM/Executor integrations in dedicated classes; `CodegenService` calls their public API only.
- Introduce new subpackages (e.g., `textmsa/services/codegen/persistence`) if code exceeds ~600 lines per file.
```

## Code Structure Patterns

### Module/Class Organization
```
1. Module docstring describing responsibility.
2. Imports grouped by the order above.
3. Logger + constants + type aliases.
4. Class definitions (agent, executor, service) with public methods first, private helpers prefixed `_`.
5. Helper functions if they belong to the module but not to a class (rare—prefer @staticmethod).
6. No executable code at import time; expose factories via functions.
```

### Function/Method Organization
```
- Validate inputs (user_id, template status, file existence) before side effects.
- Derive dependencies (file paths, env vars) next.
- Execute core logic (LLM call, Mongo query, subprocess) wrapped in try/except.
- Persist results / emit logs.
- Return DTOs converted via `codegen_*_to_dict` helpers to keep API consistent.
```

### File Organization Principles
```
- One major class per file to emphasize responsibilities.
- Keep public API (e.g., `CodegenService.generate_template`) near the top; helper methods follow.
- Hide implementation details with leading underscores; document externally-visible behaviors in README/requirements.
```

## Code Organization Principles

1. **Single Responsibility**: `CodegenService` orchestrates but delegates LLM/execution/file access to dedicated helpers.
2. **Modularity**: Config, persistence, conversations, executions should remain swappable via dependency injection (LLM client, file service, Mongo connection args).
3. **Testability**: Constructor arguments should accept fakes/mocks (`connection_string`, `llm`, `work_dir`) to facilitate unit tests without hitting real infra.
4. **Consistency**: Follow logging, exception-handling, and HTTP error patterns already present in `generate_template`, `execute_template`, etc.

## Module Boundaries

- **Service Layer (`codegen_service.py`)**
  - Owns API-facing workflows: conversations, lifecycle transitions, execution history.
  - Persists templates/executions/conversations to MongoDB collections; never touches LLM or subprocesses directly.
- **Agent Layer (`codegen_agent.py`)**
  - Encapsulates all LLM prompt/response logic and schema shaping.
  - Produces `CodegenTemplate` objects; no database knowledge.
- **Executor Layer (`codegen_executor.py`)**
  - Runs generated code in isolated working dirs; only communicates via structured results.
  - Handles environment bootstrapping (conda paths, temp dirs) without persisting state.
- **Data & Storage**
  - Mongo models define serialization; file services resolve physical paths for inputs/outputs.
  - Add new persistence backends by extending `get_file_service/get_file_manager` rather than editing executor/service internals.

Dependencies should flow downward (service → agent/executor/data/file). Agent and executor MUST NOT import `codegen_service`.

## Code Size Guidelines

- **File size**: keep each module ≤ 600 LOC; split into submodules when approaching the limit (e.g., extract `conversation_service.py`).
- **Function/method size**: target ≤ 60 LOC; refactor into helpers when error handling bloats the method.
- **Class complexity**: avoid more than 10 public methods per class; consider mixins or helper objects when workflows multiply.
- **Nesting depth**: limit to 3 levels inside a function (loops/conditionals); prefer guard clauses plus early returns to flatten control flow.

## Dashboard/Monitoring Structure

The service currently surfaces health via logs. When adding dashboards:
```
textmsa/services/codegen/observability/
├── metrics.py        # Prometheus/OpenTelemetry counters (LLM latency, execution duration)
├── tracing.py        # Common trace helpers
└── exporters/        # Optional integrations (stdout, OTLP, etc.)
```
- Metrics/traces should hook into `textmsa.logging_config` so they can be toggled via global config.
- Observability must remain optional; failing exporters must never break template generation.

## Documentation Standards

- Update `README.md` whenever a new API workflow or dependency is introduced.
- Keep `requirements.md` and this `structure.md` in sync with architectural decisions; reference them from design reviews.
- Public-facing classes/methods require docstrings describing parameters and raised exceptions.
- Complex logic (status transitions, retry loops) should include inline comments explaining rationale rather than mechanics.
- When introducing new modules, add a short section under `docs/` or the root README describing how to wire them into FastAPI routers.
