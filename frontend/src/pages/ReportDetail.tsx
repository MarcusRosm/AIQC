import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Box, Flex, Heading, Text, Badge, Button, Tabs } from '@radix-ui/themes'
import { ArrowLeftIcon } from '@radix-ui/react-icons'
import { getReport, type FullReport } from '../api/client'
import { HealingCard } from '../components/HealingCard'

const STATUS_ICON: Record<string, string> = { passed: '✅', failed: '❌', error: '⚠️', skipped: '⏭️' }

export function ReportDetail() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const [report, setReport] = useState<FullReport | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!runId) return
    getReport(runId).then(setReport).catch(() => navigate('/reports')).finally(() => setLoading(false))
  }, [runId])

  if (loading) return <Flex justify="center" pt="10"><div className="spinner" /></Flex>
  if (!report) return null

  const passed = report.execution_results.filter(r => r.status === 'passed').length
  const failed = report.execution_results.filter(r => r.status === 'failed').length
  const healed = report.heal_results.filter(r => r.status === 'success').length

  return (
    <Box>
      <Button variant="ghost" onClick={() => navigate('/reports')} mb="4" style={{ color: '#64748b', cursor: 'pointer' }}>
        <ArrowLeftIcon /> Back to Reports
      </Button>

      {/* Header */}
      <Flex direction="column" gap="1" mb="5">
        <Flex align="center" gap="3">
          <Heading size="6" style={{ color: '#e2e8f0' }}>{report.label ?? 'Pipeline Run'}</Heading>
          <Badge color={report.status === 'completed' ? 'green' : 'red'} variant="soft">
            {report.status}
          </Badge>
        </Flex>
        <Text size="1" style={{ fontFamily: 'var(--font-mono)', color: '#475569' }}>{report.run_id}</Text>
      </Flex>

      {/* Pipeline Error Banner */}
      {report.error && (
        <Box className="glass-card" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', borderColor: 'rgba(239, 68, 68, 0.3)' }} p="4" mb="6">
          <Flex align="center" gap="2" mb="2">
            <Text size="3">❌</Text>
            <Text weight="bold" style={{ color: '#fca5a5' }}>Pipeline Execution Failed</Text>
          </Flex>
          <Text size="2" style={{ color: '#f87171', fontFamily: 'var(--font-mono)' }}>{report.error}</Text>
        </Box>
      )}

      {/* Stats row */}
      <Flex gap="3" mb="6" wrap="wrap">
        {[
          { label: 'Passed', value: passed, color: '#10b981' },
          { label: 'Failed', value: failed, color: '#ef4444' },
          { label: 'Auto-healed', value: healed, color: '#f59e0b' },
          { label: 'Specs', value: report.generated_specs.length, color: '#818cf8' },
        ].map(stat => (
          <Box key={stat.label} className="glass-card" p="4" style={{ minWidth: 100, flex: '1 1 100px' }}>
            <Text size="5" weight="bold" style={{ color: stat.color, display: 'block' }}>{stat.value}</Text>
            <Text size="1" style={{ color: '#64748b' }}>{stat.label}</Text>
          </Box>
        ))}
      </Flex>

      <Tabs.Root defaultValue="tests">
        <Tabs.List>
          <Tabs.Trigger value="tests">🧪 Tests ({report.execution_results.length})</Tabs.Trigger>
          <Tabs.Trigger value="healing">🔧 Self-Healing ({report.heal_results.length})</Tabs.Trigger>
          <Tabs.Trigger value="specs">📄 Specs ({report.generated_specs.length})</Tabs.Trigger>
        </Tabs.List>

        {/* Tests tab */}
        <Tabs.Content value="tests" style={{ paddingTop: 16 }}>
          <Flex direction="column" gap="2">
            {report.execution_results.length === 0
              ? <Text size="2" style={{ color: '#475569' }}>No test results recorded.</Text>
              : report.execution_results.map((r, i) => (
                <Box key={i} className="glass-card" p="3">
                  <Flex align="center" gap="3" wrap="wrap">
                    <Text size="2">{STATUS_ICON[r.status]}</Text>
                    <Text size="2" weight="medium" style={{ color: '#c7d2fe', flex: 1 }}>{r.test_title}</Text>
                    <Text size="1" style={{ fontFamily: 'var(--font-mono)', color: '#475569' }}>{r.duration_ms}ms</Text>
                    <span className={`status-chip ${r.status}`}>{r.status}</span>
                  </Flex>
                  {r.error_message && (
                    <Box mt="2" className="code-block" style={{ fontSize: 11 }}>{r.error_message}</Box>
                  )}
                </Box>
              ))
            }
          </Flex>
        </Tabs.Content>

        {/* Healing tab */}
        <Tabs.Content value="healing" style={{ paddingTop: 16 }}>
          {report.heal_results.length === 0
            ? <Text size="2" style={{ color: '#475569' }}>No healing attempts for this run.</Text>
            : <Flex direction="column" gap="3">
                {report.heal_results.map((h, i) => <HealingCard key={i} heal={h} />)}
              </Flex>
          }
        </Tabs.Content>

        {/* Specs tab */}
        <Tabs.Content value="specs" style={{ paddingTop: 16 }}>
          <Flex direction="column" gap="4">
            {report.generated_specs.map((spec, i) => (
              <Box key={i} className="glass-card" p="4">
                <Flex align="center" gap="2" mb="3">
                  <Text size="2" weight="medium" style={{ fontFamily: 'var(--font-mono)', color: '#a5b4fc' }}>📄 {spec.filename}</Text>
                </Flex>
                <div className="code-block">{spec.content}</div>
              </Box>
            ))}
          </Flex>
        </Tabs.Content>
      </Tabs.Root>
    </Box>
  )
}
