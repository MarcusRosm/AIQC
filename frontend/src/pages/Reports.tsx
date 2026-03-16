import { useEffect, useState } from 'react'
import { Box, Flex, Heading, Text, Badge, Button } from '@radix-ui/themes'
import { useNavigate } from 'react-router-dom'
import { listReports, type ReportSummary } from '../api/client'
import { usePipelineSSE } from '../hooks/usePipelineSSE'
import { PipelineProgress } from '../components/PipelineProgress'
import { Dialog } from '@radix-ui/themes'
import { PlayIcon } from '@radix-ui/react-icons'

const STATUS_COLOR: Record<string, 'indigo' | 'green' | 'red' | 'amber' | 'gray'> = {
  completed: 'green',
  failed: 'red',
  started: 'indigo',
  tests_running: 'amber',
}

export function Reports() {
  const [reports, setReports] = useState<ReportSummary[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const { state, runId, events, error, retry, reset } = usePipelineSSE()
  const activeStage = events.length > 0 ? events[events.length - 1].stage : null
  const [retryModalOpen, setRetryModalOpen] = useState(false)

  const fetchReports = () => {
    setLoading(true)
    listReports()
      .then(setReports)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchReports()
  }, [])

  const handleRetry = async (e: React.MouseEvent, targetRunId: string) => {
    e.stopPropagation()
    reset()
    setRetryModalOpen(true)
    await retry(targetRunId)
  }

  const closeRetryModal = () => {
    setRetryModalOpen(false)
    if (state === 'done') {
      fetchReports() // Refresh if we just completed a test
    }
  }

  return (
    <Box>
      <Flex align="center" justify="between" mb="6">
        <Box>
          <Heading size="7" mb="1" style={{ background: 'linear-gradient(135deg, #a5b4fc, #818cf8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            Pipeline Reports
          </Heading>
          <Text size="2" style={{ color: '#64748b' }}>
            Historical pipeline runs and test results
          </Text>
        </Box>
        <Badge variant="soft" style={{ background: 'rgba(99,102,241,0.1)', color: '#a5b4fc' }}>
          {reports.length} run{reports.length !== 1 ? 's' : ''}
        </Badge>
      </Flex>

      {loading ? (
        <Flex justify="center" py="10"><div className="spinner" /></Flex>
      ) : reports.length === 0 ? (
        <Box className="glass-card" p="10">
          <Flex direction="column" align="center" gap="3">
            <Text size="6">📋</Text>
            <Text size="3" style={{ color: '#475569' }}>No reports yet. Run a pipeline from the Dashboard.</Text>
            <Button variant="outline" onClick={() => navigate('/')} style={{ marginTop: 8 }}>
              Go to Dashboard
            </Button>
          </Flex>
        </Box>
      ) : (
        <Flex direction="column" gap="3">
          {reports.map(r => (
            <Box
              key={r.run_id}
              className="glass-card"
              p="4"
              style={{ cursor: 'pointer', transition: 'transform 0.15s ease' }}
              onClick={() => navigate(`/reports/${r.run_id}`)}
              onMouseEnter={e => (e.currentTarget.style.transform = 'translateX(4px)')}
              onMouseLeave={e => (e.currentTarget.style.transform = 'translateX(0)')}
            >
              <Flex align="center" justify="between" wrap="wrap" gap="3">
                <Box>
                  <Flex align="center" gap="2" mb="1">
                    <Badge color={STATUS_COLOR[r.status] ?? 'gray'} variant="soft" size="1">
                      {r.status.replace('_', ' ')}
                    </Badge>
                    {r.label && <Text size="2" weight="medium" style={{ color: '#c7d2fe' }}>{r.label}</Text>}
                  </Flex>
                  <Text size="1" style={{ fontFamily: 'var(--font-mono)', color: '#475569' }}>
                    {r.run_id}
                  </Text>
                </Box>
                <Flex gap="4" align="center">
                  <Box style={{ textAlign: 'right' }}>
                    <Text size="1" style={{ color: '#64748b', display: 'block' }}>Tests</Text>
                    <Text size="2" weight="bold" style={{ color: '#e2e8f0' }}>{r.test_count}</Text>
                  </Box>
                  <Box style={{ textAlign: 'right' }}>
                    <Text size="1" style={{ color: '#64748b', display: 'block' }}>Healed</Text>
                    <Text size="2" weight="bold" style={{ color: r.heal_count > 0 ? '#fcd34d' : '#334155' }}>{r.heal_count}</Text>
                  </Box>
                  <Box style={{ textAlign: 'right' }}>
                    <Text size="1" style={{ color: '#64748b', display: 'block' }}>Started</Text>
                    <Text size="1" style={{ color: '#94a3b8' }}>{new Date(r.started_at).toLocaleString()}</Text>
                  </Box>
                  <Box>
                    <Button 
                      variant="soft" 
                      color="indigo" 
                      onClick={(e) => handleRetry(e, r.run_id)}
                      disabled={r.status === 'started' || r.status === 'tests_running'}
                    >
                      <PlayIcon /> Retry
                    </Button>
                  </Box>
                </Flex>
              </Flex>
            </Box>
          ))}
        </Flex>
      )}

      {/* Retry Modal */}
      <Dialog.Root open={retryModalOpen} onOpenChange={(open) => !open && closeRetryModal()}>
        <Dialog.Content style={{ maxWidth: 600, background: '#0d0d14', border: '1px solid rgba(255,255,255,0.1)' }}>
          <Dialog.Title style={{ color: '#c7d2fe' }}>Retrying Pipeline Run</Dialog.Title>
          <Dialog.Description size="2" mb="4" style={{ color: '#64748b' }}>
            Re-executing generated Playwright tests for {runId || 'pipeline'}...
          </Dialog.Description>

          <Box className="glass-card" p="5">
            {error ? (
              <Box p="3" style={{ background: 'rgba(239,68,68,0.1)', borderRadius: 8, border: '1px solid rgba(239,68,68,0.25)' }}>
                <Text size="1" style={{ color: '#fca5a5' }}>⚠️ {error}</Text>
              </Box>
            ) : (
              <PipelineProgress events={events} activeStage={activeStage} isDone={state === 'done'} />
            )}
          </Box>

          <Flex gap="3" mt="5" justify="end">
            <Button variant="soft" color="gray" onClick={closeRetryModal}>
              {state === 'done' || state === 'error' ? 'Close' : 'Cancel Visuals'}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
    </Box>
  )
}
