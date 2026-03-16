/**
 * API client – typed wrappers around the QA Platform REST API.
 */

const BASE = '/api'

export interface PipelineRunResponse {
  run_id: string
  status: string
}

export interface PipelineEventPayload {
  stage: string
  message: string
  payload: Record<string, unknown>
  timestamp: string
}

export interface ReportSummary {
  run_id: string
  label: string | null
  status: string
  started_at: string
  completed_at: string | null
  test_count: number
  heal_count: number
}

export interface FullReport {
  run_id: string
  label: string | null
  started_at: string
  completed_at: string | null
  status: string
  error?: string
  diff_result: unknown
  scenario_list: unknown
  generated_specs: Array<{ filename: string; content: string; scenario_ids: string[] }>
  execution_results: Array<{
    test_title: string
    spec_file: string
    status: string
    duration_ms: number
    error_message: string | null
    failing_selector: string | null
  }>
  heal_results: Array<{
    original_selector: string
    status: string
    chosen_candidate: { playwright_locator: string; confidence: number } | null
    pr_comment: string | null
    test_title: string
  }>
}

export async function startPipelineRun(
  diffText: string,
  label?: string,
  skipHealing = false
): Promise<PipelineRunResponse> {
  const res = await fetch(`${BASE}/pipeline/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ diff_text: diffText, run_label: label, skip_healing: skipHealing }),
  })
  if (!res.ok) throw new Error(`Pipeline start failed: ${res.status}`)
  return res.json()
}

export async function retryPipeline(runId: string): Promise<PipelineRunResponse> {
  const res = await fetch(`${BASE}/pipeline/retry/${runId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) throw new Error(`Pipeline retry failed: ${res.status}`)
  return res.json()
}

export function subscribePipelineStatus(
  runId: string,
  onEvent: (event: PipelineEventPayload) => void,
  onDone: () => void
): () => void {
  const es = new EventSource(`${BASE}/pipeline/status/${runId}`)
  es.addEventListener('message', (e) => {
    try { onEvent(JSON.parse(e.data)) } catch (_) {}
  })
  // Listen for all stage event types
  const stages = ['started', 'diff_analyzed', 'context_retrieved', 'scenarios_generated',
    'code_generated', 'tests_running', 'healing', 'completed', 'failed']
  stages.forEach(stage => {
    es.addEventListener(stage, (e: MessageEvent) => {
      try {
        const data = JSON.parse((e as MessageEvent).data)
        onEvent(data)
        if (stage === 'completed' || stage === 'failed') { es.close(); onDone() }
      } catch (_) {}
    })
  })
  es.onerror = () => { es.close(); onDone() }
  return () => es.close()
}

export async function listReports(): Promise<ReportSummary[]> {
  const res = await fetch(`${BASE}/reports`)
  if (!res.ok) throw new Error('Failed to fetch reports')
  return res.json()
}

export async function getReport(runId: string): Promise<FullReport> {
  const res = await fetch(`${BASE}/reports/${runId}`)
  if (!res.ok) throw new Error(`Report not found: ${runId}`)
  return res.json()
}
