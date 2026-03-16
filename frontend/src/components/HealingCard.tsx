import { Box, Flex, Text, Badge } from '@radix-ui/themes'

interface HealResultData {
  original_selector: string
  status: string
  chosen_candidate: { playwright_locator: string; confidence: number } | null
  pr_comment: string | null
  test_title: string
}

interface Props {
  heal: HealResultData
}

export function HealingCard({ heal }: Props) {
  const isSuccess = heal.status === 'success'
  const conf = heal.chosen_candidate?.confidence ?? 0
  const confClass = conf >= 0.8 ? 'high' : conf >= 0.5 ? '' : 'low'

  return (
    <Box className="glass-card" p="4" style={{ borderLeft: `3px solid ${isSuccess ? '#10b981' : '#ef4444'}` }}>
      <Flex align="center" gap="2" mb="3">
        <Text size="2">{isSuccess ? '🔧' : '⚠️'}</Text>
        <Text size="2" weight="medium" style={{ color: '#c7d2fe', flex: 1 }}>{heal.test_title}</Text>
        <Badge color={isSuccess ? 'green' : 'red'} variant="soft" size="1">
          {heal.status.replace('_', ' ')}
        </Badge>
        {isSuccess && (
          <span className={`confidence-badge ${confClass}`}>
            {(conf * 100).toFixed(1)}% confidence
          </span>
        )}
      </Flex>

      <Flex direction="column" gap="2">
        <Box>
          <Text size="1" style={{ color: '#64748b', display: 'block', marginBottom: 4 }}>❌ Broken selector</Text>
          <div className="code-block" style={{ fontSize: 11 }}>{heal.original_selector}</div>
        </Box>
        {heal.chosen_candidate && (
          <Box>
            <Text size="1" style={{ color: '#64748b', display: 'block', marginBottom: 4 }}>✅ Suggested fix</Text>
            <div className="code-block" style={{ fontSize: 11, borderColor: 'rgba(16,185,129,0.3)', color: '#6ee7b7' }}>
              {heal.chosen_candidate.playwright_locator}
            </div>
          </Box>
        )}
        {heal.pr_comment && (
          <details style={{ marginTop: 4 }}>
            <summary style={{ cursor: 'pointer', color: '#64748b', fontSize: 12 }}>View PR comment template</summary>
            <div className="code-block" style={{ fontSize: 11, marginTop: 8 }}>{heal.pr_comment}</div>
          </details>
        )}
      </Flex>
    </Box>
  )
}
