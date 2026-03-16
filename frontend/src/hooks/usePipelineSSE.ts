import { useState, useCallback, useRef } from 'react'
import { startPipelineRun, retryPipeline, subscribePipelineStatus, type PipelineEventPayload } from '../api/client'

export type PipelineState = 'idle' | 'running' | 'done' | 'error'

export function usePipelineSSE() {
  const [state, setState] = useState<PipelineState>('idle')
  const [runId, setRunId] = useState<string | null>(null)
  const [events, setEvents] = useState<PipelineEventPayload[]>([])
  const [error, setError] = useState<string | null>(null)
  const cleanupRef = useRef<(() => void) | null>(null)

  const start = useCallback(async (diffText: string, label?: string) => {
    setState('running')
    setEvents([])
    setError(null)
    setRunId(null)

    try {
      const { run_id } = await startPipelineRun(diffText, label)
      setRunId(run_id)

      const cleanup = subscribePipelineStatus(
        run_id,
        (event) => setEvents(prev => [...prev, event]),
        () => setState('done')
      )
      cleanupRef.current = cleanup
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      setState('error')
    }
  }, [])

  const retry = useCallback(async (existingRunId: string) => {
    setState('running')
    setEvents([])
    setError(null)
    setRunId(null)

    try {
      const { run_id } = await retryPipeline(existingRunId)
      setRunId(run_id)

      const cleanup = subscribePipelineStatus(
        run_id,
        (event) => setEvents(prev => [...prev, event]),
        () => setState('done')
      )
      cleanupRef.current = cleanup
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      setState('error')
    }
  }, [])

  const reset = useCallback(() => {
    cleanupRef.current?.()
    setState('idle')
    setRunId(null)
    setEvents([])
    setError(null)
  }, [])

  return { state, runId, events, error, start, retry, reset }
}
