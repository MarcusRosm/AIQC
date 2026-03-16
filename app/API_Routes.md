# Application Architecture and API Routes

This document provides a comprehensive overview of the `app` directory structure, the responsibilities of each module, and detailed documentation on every available API route including `curl` examples.

---

## Application Directory Tree

The `app` folder is structured to separate concerns following cleanly layered architecture principles. 

```text
app/
├── api/                     # FastAPI core entry points and route handlers
│   ├── app.py               # Application factory, middleware, and lifespan definitions
│   ├── routes/              # Modular API routers
│   │   ├── health.py        # Health and readiness check endpoint
│   │   ├── pipeline.py      # Triggering new pipeline runs and streaming status
│   │   └── reports.py       # Fetching and deleting historical run data
│   └── sse.py               # Server-Sent Events (SSE) broadcaster logic
├── core/                    # Global utilities, schemas, and configurations
│   ├── config.py            # Environment variables and typed static settings
│   ├── exceptions.py        # Domain-specific custom exceptions
│   ├── logging.py           # Structured logging configuration
│   └── schemas.py           # Pydantic v2 schemas for all cross-module data
├── healing/                 # Self-healing engine for broken Playwright selectors
│   ├── healer.py            # Agent that attempts fixes for failing test locators
│   └── locator_scorer.py    # Logic to map old selectors to viable new candidates
├── llm/                     # Interface with the Large Language Model platform
│   ├── client.py            # Async wrapper for the Ollama API calls
│   └── prompts.py           # Defined LLM prompts and QA guardrails
├── pipeline/                # Core AI-Driven QA execution stages
│   ├── code_generator.py    # Generates executable Python Pytest specs from scenarios
│   ├── diff_analyzer.py     # Parses Git diffs into structured file/component changes
│   ├── executor.py          # Subprocess runner for executing Pytest test suites
│   ├── orchestrator.py      # Main pipeline flow director combining all stages
│   └── scenario_generator.py # Asks the LLM to design scenarios based on diffs
├── rag/                     # Retrieval-Augmented Generation for code context
│   ├── embeddings.py        # Generates vector embeddings for code via Ollama
│   ├── indexer.py           # Scrapes repo code to populate the vector DB
│   ├── retriever.py         # Performs similarity search against the DB chunks
│   └── vector_store.py      # Wrapper around the local ChromaDB database instance
├── skills/                  # Extensibility / agents
│   └── skills_structure.md
└── README.md                # Quick-start integration guide
```

---

## API Routes & Endpoints

The AI-driven QA backend exposes several endpoints under `/api`. Below are the complete details for each available route, what they do, and how to invoke them via `curl`.

### 1. Health Checks

#### `GET /api/health`
A readiness probe to ensure the system and its dependent microservices (Ollama and ChromaDB) are functioning properly.
- **Returns**: A JSON payload evaluating readiness. `status` will be `"ok"` if all dependencies return successfully, otherwise `"degraded"`.
- **Ideal use case**: Integration with load balancers, Kubernetes probes, or CI gating before triggering tests.

**cURL Example**:
```bash
curl -X GET http://localhost:8000/api/health
```

---

### 2. Pipeline Execution

#### `POST /api/pipeline/run`
Triggers an asynchronous pipeline execution that processes a git diff, designs scenarios, writes tests, runs them, and attempts self-healing if a locator fails.
- **Request Body**:
  - `diff_text` (String, required): The raw git diff output. Must be at least 10 characters long.
  - `repo_root` (String, optional): Absolute path to the repository, used for RAG context extraction.
  - `run_label` (String, optional): Label for the specific run.
  - `skip_healing` (Boolean, optional, defaults to `false`): If `true`, the pipeline executes the tests without falling back to auto-healing.
- **Response**: Returns `202 Accepted` immediately with a unique `run_id`.

**cURL Example**:
```bash
curl -X POST http://localhost:8000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{
    "diff_text": "diff --git a/app.py b/app.py\n+ print(\"new feature\")",
    "repo_root": "/path/to/my/project",
    "run_label": "Testing Feature XYZ",
    "skip_healing": false
  }'
```

#### `GET /api/pipeline/status/{run_id}`
Establishes a Server-Sent Events (SSE) connection to stream real-time JSON updates on the progress of an executing pipeline.
- **Path Parameter**: `run_id` - The UUID retrieved from the `/run` endpoint.
- **Returns**: Live event streams detailing the current `PipelineStage` (e.g., `scenarios_generated`, `tests_running`, `completed`).

**cURL Example**:
```bash
curl -N -H "Accept: text/event-stream" http://localhost:8000/api/pipeline/status/YOUR-RUN-ID-HERE
```

---

### 3. Pipeline Reports

#### `GET /api/reports`
Lists high-level summary metadata of every previously completed or failed pipeline run currently stored on disk.
- **Returns**: A JSON array of summaries containing the `run_id`, `label`, `status`, `started_at`, completion times, and a count of executed tests.

**cURL Example**:
```bash
curl -X GET http://localhost:8000/api/reports
```

#### `GET /api/reports/{run_id}`
Retrieves the complete, unabridged execution report and results for a specific run footprint.
- **Path Parameter**: `run_id` - The unique ID of the target test run.
- **Returns**: A comprehensive JSON payload documenting original scenarios, actual generated Python source code, complete test execution statuses (Passed/Failed/Error), and detailed logs of any self-healing operations that took place.

**cURL Example**:
```bash
curl -X GET http://localhost:8000/api/reports/YOUR-RUN-ID-HERE
```

#### `DELETE /api/reports/{run_id}`
Deletes the specific JSON report of a completed run from local storage along with its records.
- **Path Parameter**: `run_id` - The unique identifier of the target test run.
- **Returns**: `204 No Content` on success.

**cURL Example**:
```bash
curl -X DELETE http://localhost:8000/api/reports/YOUR-RUN-ID-HERE
```
