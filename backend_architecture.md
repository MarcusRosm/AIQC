# AIQC Backend Architecture

The AIQC backend is an AI-driven Quality Assurance platform designed to automatically analyze git diffs, generate relevant Playwright test scenarios, write the corresponding test code, execute it, and attempt to self-heal any broken UI locators.

## 1. System Overview

The system runs as a Python-based FastAPI web application. It orchestrates a multi-step pipeline integrating local LLMs (via Ollama), a Vector Database (ChromaDB) for Retrieval-Augmented Generation (RAG), and a local Playwright execution environment.

```mermaid
flowchart TD
    Client[Client App/Browser]
    API[FastAPI Router & SSE]
    
    subgraph Core Pipeline
        Orchestrator[Pipeline Orchestrator]
        DiffAnalyzer[Diff Analyzer]
        ScenGen[Scenario Generator]
        CodeGen[Code Generator]
        Executor[Playwright Executor]
        Healer[Self-Healing Engine]
    end
    
    subgraph RAG System
        Retriever[Context Retriever]
        Chroma[(ChromaDB)]
    end
    
    subgraph External Services
        Ollama[Ollama Local LLM]
    end

    Client -- HTTP / SSE -> API
    API --> Orchestrator
    
    Orchestrator --> DiffAnalyzer
    Orchestrator --> Retriever
    Orchestrator --> ScenGen
    Orchestrator --> CodeGen
    Orchestrator --> Executor
    Orchestrator --> Healer
    
    Retriever <--> Chroma
    
    ScenGen <--> Ollama
    CodeGen <--> Ollama
    Healer <--> Ollama
```

## 2. Core Components

- **API & SSE (`app.api`)**: FastAPI application providing REST endpoints and Server-Sent Events (SSE) for real-time pipeline status updates.
- **Pipeline Orchestrator (`app.pipeline.orchestrator`)**: The controller that drives the sequential execution of the QA steps.
- **Diff Analyzer (`app.pipeline.diff_analyzer`)**: Parses git diffs to identify changed files, affected routes, and components.
- **RAG System (`app.rag`)**: Uses `ContextRetriever` and `VectorStore` (ChromaDB) to fetch relevant codebase context to inform the LLM about existing utilities or models.
- **Scenario & Code Generators (`app.pipeline.scenario_generator` & `code_generator`)**: Interfaces with the local LLM (`LLMClient`) to dynamically generate targeted JSON scenarios and format them into executable Playwright Pytest files.
- **Test Executor (`app.pipeline.executor`)**: Programmatically runs `pytest` on the generated Playwright specs and captures execution results.
- **Self-Healing Engine (`app.healing.healer`)**: Evaluates failing test execution results. Uses a two-tier approach (a fast heuristic `LocatorScorer` and an AI-assist fallback) to propose new operational selectors for broken locators.

## 3. Class Diagram

This diagram visualizes the main relationships between the core Pydantic domain models (`schemas.py`) and the primary processing classes.

```mermaid
classDiagram
    class PipelineRun {
        +String run_id
        +PipelineStage status
        +DiffResult diff_result
        +TestScenarioList scenario_list
        +List~GeneratedSpec~ generated_specs
        +List~ExecutionResult~ execution_results
    }
    
    class Orchestrator {
        -LLMClient llm
        -ScenarioGenerator scenario_gen
        -CodeGenerator code_gen
        +run_pipeline(request)
    }

    class LLMClient {
        +generate(prompt)
        +chat(messages)
        +generate_json(prompt)
    }

    class ScenarioGenerator {
        +generate(diff, context) TestScenarioList
    }

    class PlaywrightCodeGenerator {
        +generate(scenarios, context) List~GeneratedSpec~
    }

    class SelfHealingEngine {
        +heal(failure: ExecutionResult) HealResult
    }
    
    Orchestrator --> PipelineRun : Manages
    Orchestrator --> ScenarioGenerator : Uses
    Orchestrator --> PlaywrightCodeGenerator : Uses
    Orchestrator --> SelfHealingEngine : Uses
    Orchestrator --> ContextRetriever : Uses
    
    ScenarioGenerator --> LLMClient : Prompts
    PlaywrightCodeGenerator --> LLMClient : Prompts
    SelfHealingEngine --> LLMClient : Prompts

    ScenarioGenerator ..> TestScenarioList : Produces
    PlaywrightCodeGenerator ..> GeneratedSpec : Produces
```

## 4. Pipeline Execution Sequence

The `Orchestrator` triggers a sequential flow of dependent events, passing structured `Pydantic` schemas representing the result of one step to the input of the next.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant API as FastAPI / SSE
    participant Orch as Orchestrator
    participant Diff as Diff Analyzer
    participant RAG as Context Retriever
    participant LLM as LLMClient (Ollama)
    participant Exec as Test Executor
    participant Heal as Self-Healing Engine

    User->>API: POST /api/v1/pipeline (git diff)
    API->>Orch: Start Pipeline Run
    API-->>User: Return Run ID & SSE Stream
    
    Orch->>Diff: parse_diff(raw_diff)
    Diff-->>Orch: DiffResult
    Orch->>API: yield SSE (DIFF_ANALYZED)
    
    Orch->>RAG: retrieve_context(DiffResult)
    RAG-->>Orch: List<CodeSnippets>
    Orch->>API: yield SSE (CONTEXT_RETRIEVED)
    
    Orch->>LLM: generate_json(diff, context)
    note right of LLM: Step 3: Scenario Generation
    LLM-->>Orch: TestScenarioList (JSON)
    Orch->>API: yield SSE (SCENARIOS_GENERATED)
    
    Orch->>LLM: generate_json(scenarios, context)
    note right of LLM: Step 4: Code Generation
    LLM-->>Orch: List<GeneratedSpec>
    Orch->>API: yield SSE (CODE_GENERATED)
    
    Orch->>Exec: run_tests(GeneratedSpec)
    note right of Exec: Spawns pytest subprocess
    Exec-->>Orch: List<ExecutionResult>
    Orch->>API: yield SSE (TESTS_RUNNING Finished)

    loop For each failed ExecutionResult
        Orch->>Heal: heal(failed_test)
        Heal->>LLM: suggest_fixes(DOM, original_selector)
        LLM-->>Heal: HealCandidate[]
        Heal-->>Orch: HealResult
    end
    
    Orch->>API: yield SSE (HEALING Finished / COMPLETED)
    Orch-->>API: Persist PipelineRun to disk
```

## 5. Schema & Data Flow Structure

The backend makes extensive use of `Pydantic v2` to enforce strict contracts between the different lifecycle steps. The schemas act as the single source of truth for the data shapes generated by the LLM prompts and consumed by the processing components:

1. `PipelineRunRequest` ➔ `DiffResult`
2. `DiffResult` + `List[str]` (Context) ➔ `TestScenarioList`
3. `TestScenarioList` + `List[str]` ➔ `GeneratedSpec` (Playwright Test Files)
4. `GeneratedSpec` ➔ `ExecutionResult`
5. `ExecutionResult` (if failed) ➔ `HealResult` (AI/Heuristic healed locator)
