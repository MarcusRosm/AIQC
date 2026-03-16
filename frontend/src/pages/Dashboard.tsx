import { useState } from 'react'
import { Box, Flex, Heading, Text, Button, TextField, Separator } from '@radix-ui/themes'
import { PlayIcon, ReloadIcon } from '@radix-ui/react-icons'
import { usePipelineSSE } from '../hooks/usePipelineSSE'
import { PipelineProgress } from '../components/PipelineProgress'

const STAGE_ORDER = [
  'started', 'diff_analyzed', 'context_retrieved', 'scenarios_generated',
  'code_generated', 'tests_running', 'healing', 'completed',
]

const STAGE_LABELS: Record<string, string> = {
  started: '🚀 Pipeline started',
  diff_analyzed: '🔍 Diff analyzed',
  context_retrieved: '📚 Context retrieved',
  scenarios_generated: '🧠 Scenarios generated',
  code_generated: '📝 Playwright code generated',
  tests_running: '▶️ Tests running',
  healing: '🔧 Self-healing',
  completed: '✅ Completed',
  failed: '❌ Failed',
}

export function Dashboard() {
  const [diff, setDiff] = useState('')
  const [label, setLabel] = useState('')
  const { state, runId, events, error, start, reset } = usePipelineSSE()

  const activeStage = events.length > 0 ? events[events.length - 1].stage : null

  const handleStart = async () => {
    if (!diff.trim()) return
    await start(diff.trim(), label || undefined)
  }

  return (
    <Box>
      {/* Header */}
      <Flex direction="column" gap="1" mb="6">
        <Heading size="7" style={{ background: 'linear-gradient(135deg, #a5b4fc, #818cf8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          AI QA Pipeline
        </Heading>
        <Text size="2" style={{ color: '#64748b' }}>
          Paste a git diff to generate test scenarios, Playwright specs, and trigger self-healing.
        </Text>
      </Flex>

      <Flex gap="6" align="start" wrap="wrap">
        {/* Input Panel */}
        <Box className="glass-card" p="5" style={{ flex: '1 1 400px', minWidth: 320 }}>
          <Heading size="3" mb="4" style={{ color: '#c7d2fe' }}>📋 Git Diff Input</Heading>

          <Flex direction="column" gap="3">
            <Box>
              <Text size="1" mb="1" style={{ color: '#64748b', display: 'block' }}>Run label (optional)</Text>
              <TextField.Root
                value={label}
                onChange={e => setLabel(e.target.value)}
                placeholder="e.g. PR-123 auth refactor"
                disabled={state === 'running'}
                style={{ background: '#0d0d14', borderColor: 'rgba(255,255,255,0.09)' }}
              />
            </Box>

            <Box>
              <Text size="1" mb="1" style={{ color: '#64748b', display: 'block' }}>Git diff</Text>
              <textarea
                className="diff-input"
                value={diff}
                onChange={e => setDiff(e.target.value)}
                placeholder={'diff --git a/src/auth.py b/src/auth.py\n--- a/src/auth.py\n+++ b/src/auth.py\n@@ -1,5 +1,15 @@\n...'}
                disabled={state === 'running'}
              />
            </Box>

            <Flex gap="2">
              {state === 'idle' || state === 'error' ? (
                <Button
                  onClick={handleStart}
                  disabled={!diff.trim()}
                  style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', cursor: 'pointer', flex: 1 }}
                  id="run-pipeline-btn"
                >
                  <PlayIcon /> Run Pipeline
                </Button>
              ) : (
                <Button variant="outline" onClick={reset} style={{ flex: 1 }} id="reset-pipeline-btn">
                  <ReloadIcon /> Reset
                </Button>
              )}
            </Flex>

            {error && (
              <Box p="3" style={{ background: 'rgba(239,68,68,0.1)', borderRadius: 8, border: '1px solid rgba(239,68,68,0.25)' }}>
                <Text size="1" style={{ color: '#fca5a5' }}>⚠️ {error}</Text>
              </Box>
            )}

            {runId && (
              <Box p="2" style={{ background: 'rgba(99,102,241,0.08)', borderRadius: 6, border: '1px solid rgba(99,102,241,0.2)' }}>
                <Text size="1" style={{ color: '#64748b' }}>Run ID: </Text>
                <Text size="1" style={{ fontFamily: 'var(--font-mono)', color: '#a5b4fc' }}>{runId}</Text>
              </Box>
            )}
          </Flex>
        </Box>

        {/* Progress Panel */}
        <Box className="glass-card" p="5" style={{ flex: '1 1 400px', minWidth: 320 }}>
          <Heading size="3" mb="4" style={{ color: '#c7d2fe' }}>📡 Pipeline Progress</Heading>

          {state === 'idle' ? (
            <Flex direction="column" align="center" justify="center" py="8" gap="3">
              <Text size="6">🔬</Text>
              <Text size="2" style={{ color: '#475569' }}>Awaiting diff input…</Text>
            </Flex>
          ) : (
            <PipelineProgress events={events} activeStage={activeStage} isDone={state === 'done'} />
          )}
        </Box>
      </Flex>

      {/* Event log */}
      {events.length > 0 && (
        <Box className="glass-card" mt="5" p="5">
          <Heading size="3" mb="3" style={{ color: '#c7d2fe' }}>📜 Event Log</Heading>
          <Flex direction="column" gap="2">
            {events.map((ev, i) => (
              <Flex key={i} gap="3" align="start">
                <Text size="1" style={{ fontFamily: 'var(--font-mono)', color: '#475569', flexShrink: 0 }}>
                  {new Date(ev.timestamp).toLocaleTimeString()}
                </Text>
                <Text size="1" style={{ color: '#64748b', flexShrink: 0, minWidth: 18 }}>
                  {STAGE_LABELS[ev.stage]?.split(' ')[0] ?? '•'}
                </Text>
                <Text size="1" style={{ color: '#94a3b8' }}>{ev.message}</Text>
              </Flex>
            ))}
          </Flex>
        </Box>
      )}
    </Box>
  )
}
