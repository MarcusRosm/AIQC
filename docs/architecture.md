# AI-Driven QA Platform Architecture

This document outlines the architecture of the AI-Driven QA Platform, focusing on the `PipelineOrchestrator` and how it interacts with the rest of the system to process incoming code diffs, generate tests, execute them, and automatically heal broken locators.

## Core Component Diagram

The **PipelineOrchestrator** acts as a central director, ensuring the Single Responsibility Principle is followed by delegating distinct phases of test generation and execution to dedicated services. By using dependency injection, these components can be mocked during unit testing or updated independently.

```mermaid
classDiagram
    class PipelineOrchestrator {
        +run(request: PipelineRunRequest) AsyncIterator~PipelineEvent~
        +retry_execution(run_id: str) AsyncIterator~PipelineEvent~
        -_save_report(run: PipelineRun)
    }
  
    class DiffAnalyzer {
        +analyze(diff_text: str) DiffResult
    }
  
    class ContextRetriever {
        +retrieve(diff: DiffResult, top_k: int) List~str~
    }
  
    class ScenarioGenerator {
        +generate(diff: DiffResult, context: List~str~) ScenarioList
    }
  
    class PlaywrightCodeGenerator {
        +generate(scenario_list: ScenarioList, context: List~str~) List~GeneratedSpec~
    }
  
    class PlaywrightExecutor {
        +run(spec_paths: List~Path~) List~ExecutionResult~
    }
  
    class SelfHealingEngine {
        +heal(failure: ExecutionResult) HealResult
    }

    PipelineOrchestrator --> DiffAnalyzer : 1. Analyzes diff
    PipelineOrchestrator --> ContextRetriever : 2. Retrieves context via RAG
    PipelineOrchestrator --> ScenarioGenerator : 3. Uses LLM for scenarios
    PipelineOrchestrator --> PlaywrightCodeGenerator : 4. Uses LLM for code
    PipelineOrchestrator --> PlaywrightExecutor : 5. Runs Pytest Playwright
    PipelineOrchestrator --> SelfHealingEngine : 6. Attempts auto-healing
```

---

## Standard Pipeline Run Sequence

The standard pipeline runs asynchronously via FastAPI's `BackgroundTasks`, communicating its real-time progress to the client via Server-Sent Events (SSE).

When a user submits a Git diff via the Frontend Dashboard, the backend immediately acknowledges the request (HTTP 202) and returns a unique `run_id`. The client uses this ID to open an EventSource connection, receiving a live stream as the orchestrator yields events stage-by-stage.

```mermaid
sequenceDiagram
    actor Client
    participant API as API Router
    participant BG as BackgroundTasks
    participant Orch as PipelineOrchestrator
    participant SSE as SSE Event Bus
  
    Client->>API: POST /api/pipeline/run 'diff_text'
    API->>SSE: create_bus'run_id'
    API->>BG: add_task'_run_pipeline'
    API-->>Client: 202 Accepted { "run_id": "uuid" }
  
    Client->>API: GET /api/pipeline/status/{run_id}
    API-->>Client: EventSource stream opened
  
    BG->>Orch: run'request'
  
    Orch->>Orch: Step 1: DiffAnalyzer
    Orch->>SSE: yield DIFF_ANALYZED
    SSE-->>Client: Event: diff_analyzed
  
    Orch->>Orch: Step 2: ContextRetriever
    Orch->>SSE: yield CONTEXT_RETRIEVED
    SSE-->>Client: Event: context_retrieved
  
    Orch->>Orch: Step 3: ScenarioGenerator
    Orch->>SSE: yield SCENARIOS_GENERATED
    SSE-->>Client: Event: scenarios_generated
  
    Orch->>Orch: Step 4: CodeGenerator
    Orch->>SSE: yield CODE_GENERATED
    SSE-->>Client: Event: code_generated
  
    Orch->>Orch: Step 5: PlaywrightExecutor
    Orch->>SSE: yield TESTS_RUNNING
    SSE-->>Client: Event: tests_running
  
    opt If test(s) fail due to locator timeout
        Orch->>Orch: Step 6: SelfHealingEngine
        Orch->>SSE: yield HEALING
        SSE-->>Client: Event: healing
    end
  
    Orch->>Orch: _save_report'run' 'persists to JSON'
    Orch->>SSE: yield COMPLETED
    SSE-->>Client: Event: completed
```

---

## Manual Retry Sequence

If a test fails due to unstable environments or LLM syntax errors, developers can directly fix the generated code on disk.

When the user clicks the "Retry" button on the UI, a parallel endpoint is triggered that skips the LLM generation (Steps 1 through 4) and directly executes the Playwright runner on the pre-existing files, maintaining the same `run_id`.

```mermaid
sequenceDiagram
    actor Client
    participant API as API Router
    participant BG as BackgroundTasks
    participant Orch as PipelineOrchestrator
    participant SSE as SSE Event Bus
  
    Client->>API: POST /api/pipeline/retry/{run_id}
    API->>SSE: create_bus(run_id)
    API->>BG: add_task(_retry_pipeline)
    API-->>Client: 202 Accepted { "run_id": "uuid" }
  
    Client->>API: GET /api/pipeline/status/{run_id}
    API-->>Client: EventSource stream opened
  
    BG->>Orch: retry_execution(run_id)
  
    Orch->>Orch: Load existing report JSON from disk
    Orch->>SSE: yield STARTED
    SSE-->>Client: Event: started
  
    Note over Orch,SSE: Generation steps are intentionally skipped!
  
    Orch->>Orch: Step 5: PlaywrightExecutor
    Orch->>SSE: yield TESTS_RUNNING
    SSE-->>Client: Event: tests_running
  
    opt If test(s) fail due to locator timeout
        Orch->>Orch: Step 6: SelfHealingEngine
        Orch->>SSE: yield HEALING
        SSE-->>Client: Event: healing
    end
  
    Orch->>Orch: _save_report(run) (overwrites old execution payload)
    Orch->>SSE: yield COMPLETED
    SSE-->>Client: Event: completed
```

## System Resiliency and Persistence

- **Stateless Execution:** State during execution exists in memory, but at the end of the run it is persisted entirely into flat `.json` files in the `/data/reports` directory. By not relying on a strict relational datastore for run states, the architecture avoids complex data migration and makes manual inspection easy for developers.
- **SSE Fallbacks:** The Server-Sent Events architecture enables the Frontend to accurately trace status in real-time. If the browser disconnects during the stream, the orchestrator continues uninhibited mapping its findings to disk. Upon reconnecting, the React application reads the finished JSON blob from disk, ensuring no data loss on the frontend.
