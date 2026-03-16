Here's a concrete, end-to-end breakdown of how this platform integrates with **any** GitHub project:

---

## The Full Picture

```
┌─────────────────────────────────────────────────────────────┐
│  YOUR MACHINE (always running)                              │
│                                                             │
│  ┌──────────┐  ┌────────────────┐  ┌───────────────────┐   │
│  │  Ollama   │  │ FastAPI Server │  │  ChromaDB          │   │
│  │ :11434    │  │ :8000          │  │  (in-process)      │   │
│  │           │◄─┤                │──┤                    │   │
│  │ granite4  │  │ Pipeline       │  │ Repo vectors       │   │
│  │ bge-m3    │  │ orchestrator   │  │ (cosine search)    │   │
│  └──────────┘  └───────┬────────┘  └───────────────────┘   │
│                        │                                    │
│                        │ SSE events                         │
│                        ▼                                    │
│                ┌───────────────┐                            │
│                │ React UI      │                            │
│                │ :5173         │                            │
│                └───────────────┘                            │
└─────────────────────────────────────────────────────────────┘
         ▲
         │ HTTP (POST /api/pipeline/run)
         │
┌────────┴────────────────────────────────────────────────────┐
│  GITHUB (any repo)                                          │
│                                                             │
│  Developer opens PR → GitHub Actions fires                  │
│                                                             │
│  1. git diff extracted                                      │
│  2. diff posted to your FastAPI server                      │
│  3. Pipeline runs Steps 1-6                                 │
│  4. Results posted as PR comment                            │
└─────────────────────────────────────────────────────────────┘
```

---

## What each step actually does to **external** repos

| Step | Input | What Happens | Needs the target app running? |
|------|-------|-------------|------|
| **1. Diff Analysis** | Raw `git diff` text | Regex parses changed files, functions, routes, components | ❌ No |
| **2. RAG Context** | Diff summary | Embeds the summary → queries ChromaDB for similar code from the target repo (if indexed) | ❌ No (but indexing the repo first makes this useful) |
| **3. Scenario Gen** | Diff + context | Ollama generates structured test scenarios (happy/negative/edge/security) | ❌ No |
| **4. Code Gen** | Scenarios | Ollama generates `.spec.ts` Playwright TypeScript files | ❌ No |
| **5. Execution** | `.spec.ts` files | Runs `npx playwright test` → navigates to `BASE_URL` in a browser | ✅ **Yes** — the target app must be accessible |
| **6. Self-Healing** | Failed selector + live DOM | Scores DOM candidates, retries, generates PR comment fix | ✅ **Yes** — needs live DOM |

**Steps 1–4 work for any repo, anywhere, with zero setup.** You just send a diff.

**Steps 5–6 require the target application to be running** at a reachable URL (localhost in CI, staging, etc.).

---

## Three integration modes

### Mode A: Manual / Dashboard (simplest)
1. Copy a `git diff` from any repo
2. Paste it in the React UI at `http://localhost:5173`
3. Get scenarios + generated specs immediately (Steps 1–4)
4. Optionally start the target app and run the specs (Steps 5–6)

### Mode B: GitHub Actions (automated per-PR)
The [.github/workflows/qa-pipeline.yml](cci:7://file:///Users/mrosato/Documents/projects/tests/QC/.github/workflows/qa-pipeline.yml:0:0-0:0) workflow goes into the **target repo**. It needs:

| What | Where |
|------|-------|
| The workflow file | Target repo → `.github/workflows/` |
| The QA platform | Either as a **git submodule**, or deployed as a **remote service** |
| `OLLAMA_BASE_URL` secret | Points to Ollama (self-hosted runner, or cloud VM) |
| `BASE_URL` secret | Where the target app runs in CI (e.g. `http://localhost:3000`) |

The CI flow: PR opened → diff extracted → `POST /api/pipeline/run` → pipeline runs → healing suggestions posted as PR comment.

### Mode C: API-only (for custom CI systems)
Call the REST API directly from any CI (GitLab, Jenkins, CircleCI):
```bash
# Start a run
curl -X POST http://your-server:8000/api/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"diff_text": "$(git diff HEAD~1)"}'

# Stream events
curl -N http://your-server:8000/api/pipeline/status/<run_id>
```

---

## What makes the RAG context valuable for external repos

By default, ChromaDB is empty. For **best results** with a new repo, you'd index it first:
- The `RepoIndexer` walks the repo's source files, chunks them, embeds with bge-m3, and stores in ChromaDB
- Then when a diff comes in, the retriever surfaces **existing page objects, test patterns, component structures** from that specific repo
- Without indexing, Steps 3–4 still work, but the LLM only has the diff to reason about (no historical context)

**Think of indexing as "teaching the platform about a specific project."** You only need to do it once (and re-run on major changes).

---

## API Reference

The platform provides a RESTful API for integration with CI/CD pipelines and external tools.

### 1. Health & Readiness
**`GET /api/health`**
Verifies the connectivity to Ollama and the status of the local ChromaDB vector store.

- **Returns**: JSON object with `status` ("ok" or "degraded"), dependency flags, and model names.
- **Example**:
  ```bash
  curl http://localhost:8000/api/health
  ```

### 2. Pipeline Orchestration
**`POST /api/pipeline/run`**
Starts a new AI-driven QA pipeline for a specific code change.

- **Request Body**:
  - `diff_text` (string, required): Raw git diff text (min 10 chars).
  - `repo_root` (string, optional): Absolute path to the repo for context retrieval.
  - `run_label` (string, optional): A descriptive name for this specific execution.
- **Returns**: `202 Accepted` with a `run_id`.
- **Example**:
  ```bash
  curl -X POST http://localhost:8000/api/pipeline/run \
    -H "Content-Type: application/json" \
    -d '{
      "diff_text": "diff --git a/app/file... \n+ added input validation",
      "repo_root": "/Users/mrosato/Documents/projects/tests/QC",
      "run_label": "PR #42 Validation"
    }'
  ```

**`GET /api/pipeline/status/{run_id}`**
A Server-Sent Events (SSE) stream that publishes real-time progress events.

- **Example**:
  ```bash
  curl -N http://localhost:8000/api/pipeline/status/0986734f-f580-4fe4-86ad-753edffbd59b
  ```

### 3. Reports & History
**`GET /api/reports`**
Lists summaries of all completed or failed pipeline runs stored on disk.

- **Example**:
  ```bash
  curl http://localhost:8000/api/reports
  ```

**`GET /api/reports/{run_id}`**
Retrieves the full detailed execution report including test results and self-healing suggestions.

- **Example**:
  ```bash
  curl http://localhost:8000/api/reports/0986734f-f580-4fe4-86ad-753edffbd59b
  ```

**`DELETE /api/reports/{run_id}`**
Deletes the specified report from disk.

- **Example**:
  ```bash
  curl -X DELETE http://localhost:8000/api/reports/0986734f-f580-4fe4-86ad-753edffbd59b
  ```