# AI-Driven QA Platform 🧬

An **AI-powered QA platform** with self-healing Playwright tests. Automatically analyses git diffs, generates test scenarios using a local LLM, writes Playwright TypeScript specs, and heals broken selectors.

---

## Architecture – 6-Step Pipeline

```
Developer PR → CI Trigger → Diff Analyzer (Step 1)
   → RAG Context (Step 2) → LLM Scenario Gen (Step 3)
   → Playwright Code Gen (Step 4) → Test Execution (Step 5)
   → Self-Healing Engine (Step 6) → Coverage Report
```

| Component   | Tech                                      |
| ----------- | ----------------------------------------- |
| Backend API | FastAPI + uvicorn + uvloop                |
| LLM         | Ollama `granite4:3b` (AsyncClient) |
| Embeddings  | Ollama `bge-m3`                         |
| Vector DB   | ChromaDB (persistent, cosine similarity)  |
| Test runner | Playwright (TypeScript)                   |
| Frontend    | React 18 + Vite + Radix UI (dark mode)    |
| CI/CD       | GitHub Actions                            |

---

## Quick Start

### Prerequisites

- Python 3.14+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com/) running locally

```bash
# 1. Pull required models
ollama pull granite4:3b
ollama pull bge-m3

# 2. Install Python deps
uv sync

# 3. Start the API server
uv run python main.py

# 4. (Optional) Index your repo into ChromaDB
# POST /api/... or use the CLI (coming soon)

# 5. Start the frontend
cd frontend && npm install && npm run dev
# → http://localhost:5173
```

### Run tests

```bash
uv run pytest tests/ -v
```

### Using the pipeline

1. Open [http://localhost:5173](http://localhost:5173)
2. Paste a `git diff` into the text area
3. Click **Run Pipeline**
4. Watch real-time SSE events as the pipeline progresses
5. View generated specs and healing suggestions in **Reports**

### API Docs

- Swagger UI: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
- Health check: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## Configuration

All settings can be overridden via environment variables:

| Variable                      | Default                    | Description                                      |
| ----------------------------- | -------------------------- | ------------------------------------------------ |
| `OLLAMA_BASE_URL`           | `http://localhost:11434` | Ollama server URL                                |
| `OLLAMA_LLM_MODEL`          | `granite4:dense`         | LLM model name                                   |
| `OLLAMA_EMBED_MODEL`        | `bge-m3`                 | Embedding model                                  |
| `CHROMA_PATH`               | `./data/chroma`          | ChromaDB persistence path                        |
| `GENERATED_TESTS_DIR`       | `./generated_tests`      | Where .spec.ts files are written                 |
| `HEAL_CONFIDENCE_THRESHOLD` | `0.65`                   | Minimum heuristic confidence before LLM fallback |
| `API_PORT`                  | `8000`                   | API server port                                  |
| `DEBUG`                     | `false`                  | Enable reload + permissive CORS                  |

---

## Project Structure

```
QC/
├── app/
│   ├── core/          # Config, logging, exceptions, schemas
│   ├── pipeline/      # Steps 1,3,4,5 + orchestrator
│   ├── rag/           # ChromaDB embeddings, indexer, retriever
│   ├── llm/           # Ollama client + prompt templates
│   ├── healing/       # Locator scorer + self-healing engine
│   └── api/           # FastAPI app, routes, SSE bus
├── frontend/          # React + Vite + Radix UI dashboard
├── tests/             # Unit + integration tests
├── generated_tests/   # Output: LLM-generated .spec.ts files
├── data/              # ChromaDB storage + run reports
├── scripts/           # run_pipeline.sh
└── .github/workflows/ # GitHub Actions CI
```

## Self-Healing Algorithm

The **LocatorScorer** uses weighted attribute similarity:

| Signal                          | Weight |
| ------------------------------- | ------ |
| `id` exact match              | +0.40  |
| `aria-label` / `name` fuzzy | +0.30  |
| Text content fuzzy              | +0.20  |
| CSS class overlap               | +0.10  |
| `data-testid` exact (bonus)   | +0.50  |

If heuristic confidence < threshold, the **LLM is called as a fallback** with the broken selector + DOM snapshot.

On success → generates a PR comment suggestion with the new locator and confidence score.

---

## Can it test any GitHub project?

**Yes — with one important condition:** the platform is **LLM-driven and diff-driven**, meaning it generates tests from code understanding alone. It does **not** require you to own or fork the target project. However, there are two distinct modes:

### ✅ What it can always do (no app access required)
- Accept any `git diff` text and **generate test scenarios** (Step 3) — it reads your code changes and reasons about what to test
- **Generate Playwright `.spec.ts` code** (Step 4) — produces test files ready to run
- **Analyse the diff** for changed routes, functions, components (Step 1)

### ⚠️ What requires the **target app to be running**
- **Step 5: Executing tests** — Playwright must connect to a live browser/app (needs a `BASE_URL` to navigate to). Without the app running, specs are generated but will fail at the `page.goto(...)` level.
- **Step 6: Self-healing** — requires capturing a DOM snapshot from a real browser session.

So: **test generation works universally. Test execution requires the target app running somewhere** (localhost, staging, or a CI Docker container).

---

## What runs locally (on your machine)

| Component | What it does | Port |
|-----------|-------------|------|
| **Ollama** | Serves the LLM (`granite4:3b`) and embedding model (`bge-m3`). Already running on your machine. | `11434` |
| **FastAPI backend** (`uv run python main.py`) | Orchestrates the full pipeline. Receives diffs via REST, streams SSE events, saves reports. | `8000` |
| **ChromaDB** | Runs embedded inside the FastAPI process — no separate server needed. Stores repo context vectors in `./data/chroma`. | *(in-process)* |
| **React frontend** (`npm run dev`) | Dashboard UI. Connects to the FastAPI backend via the Vite proxy. | `5173` |

Playwright runs on-demand as a **subprocess** launched by the executor — no persistent process.

**Nothing else runs locally.** No Redis, no Postgres, no Docker required.

---

## Integrating the GitHub Actions workflow with any project

The workflow in `.github/workflows/qa-pipeline.yml` is self-contained. Here's what you need to do to drop it into **any GitHub repository**:

### Step 1 — Copy the workflow file
```bash
# In the target repo:
mkdir -p .github/workflows
cp /path/to/QC/.github/workflows/qa-pipeline.yml .github/workflows/
```

### Step 2 — Copy the QA platform itself
The platform needs to live alongside the target project, or (better) as a **Git submodule or separate service deployment**. The cleanest integration:

```
your-project/
├── src/                   ← your app code
├── .github/
│   └── workflows/
│       └── qa-pipeline.yml   ← references the QA platform
└── qa-platform/           ← this QC repo, as a submodule
    ├── app/
    ├── main.py
    └── ...
```

Or deploy the FastAPI backend to a persistent server (e.g. a Render/Railway free tier) and call it via HTTP from any CI.

### Step 3 — Set GitHub Secrets / env vars
In the target repo → *Settings → Secrets and variables → Actions*:

| Secret | Value |
|--------|-------|
| `OLLAMA_BASE_URL` | URL of your Ollama instance (self-hosted runner or cloud) |
| `BASE_URL` | The URL where your target app runs in CI (e.g. `http://localhost:3000`) |

### Step 4 — The workflow triggers automatically
The workflow fires on every `pull_request`. The CI:
1. Extracts the `git diff` of the PR
2. Posts it to `POST /api/pipeline/run`
3. Streams SSE until `completed` or `failed`
4. Posts healing suggestions as a PR comment

### Key requirement: Ollama in CI
Ollama must be reachable from the CI runner. The workflow currently uses a **Docker service container** (`ollama/ollama:latest`). On GitHub Actions free runners this will work, but pulling large models (like `granite4:3b`) in CI is slow. Options:

1. **Use a self-hosted GitHub runner** on a machine where Ollama is pre-installed (fastest)
2. **Use a smaller/faster model** — swap `granite4:3b` for `qwen2.5:1.5b` or `phi3:mini` via the `OLLAMA_LLM_MODEL` env var for CI speed
3. **Point to a remote Ollama instance** via `OLLAMA_BASE_URL` secret pointing to a cloud VM

---

`BASE_URL` is currently **not stored** as a platform-level config variable — it only exists in two places:

1. **In the generated Playwright specs** — the LLM prompt in [app/llm/prompts.py](cci:7://file:///Users/mrosato/Documents/projects/tests/QC/app/llm/prompts.py:0:0-0:0) instructs the LLM to emit this in generated code:
   ```typescript
   page.goto(process.env.BASE_URL ?? 'http://localhost:3000')
   ```
   So it's a **Playwright-side env var**, read at test runtime by Node.js.

2. **In the GitHub Actions workflow** — it would be set as a secret/env override on the CI runner.

### How to set it

**Locally** (when running generated specs):
```bash
BASE_URL=http://localhost:3000 npx playwright test generated_tests/**/*.spec.ts
```

**In CI** (GitHub Actions), add to the workflow env block or as a repository secret:
```yaml
env:
  BASE_URL: http://localhost:3000
```

**It's not in [app/core/config.py](cci:7://file:///Users/mrosato/Documents/projects/tests/QC/app/core/config.py:0:0-0:0)** because `BASE_URL` belongs to the **target application** being tested, not to the QA platform itself. The platform doesn't navigate to the target app — Playwright does. So it's a Node.js/Playwright env var, not a Python one.

---

[scripts/run_pipeline.sh](cci:7://file:///Users/mrosato/Documents/projects/tests/QC/scripts/run_pipeline.sh:0:0-0:0) is a **local developer convenience script** — a one-command way to boot the entire platform and optionally trigger a pipeline run. Here's what it does step by step:

| Line | What it does |
|------|-------------|
| `uv sync` | Installs/updates Python dependencies |
| `--reset-db` flag | If passed, wipes `data/chroma/` to force a clean ChromaDB re-index |
| `curl localhost:11434` | Checks that Ollama is running, warns if not |
| `uv run python main.py &` | Starts the FastAPI server in the background (skips if already running) |
| `--diff <file>` flag | If passed, reads the file, POSTs its content to `POST /api/pipeline/run`, and streams SSE events live in the terminal |

### Usage examples

```bash
# Just start the server (no diff)
./scripts/run_pipeline.sh

# Start server + run pipeline with a diff file
./scripts/run_pipeline.sh --diff my_changes.diff

# Full reset + run
./scripts/run_pipeline.sh --reset-db --diff my_changes.diff
```

**Without the `--diff` flag** it just boots the server and tells you to open `http://localhost:8000/api/docs` or the React frontend. It's basically a shortcut so you don't have to remember multiple commands every time you sit down to develop.
