import { Box, Flex, Text, Badge } from '@radix-ui/themes'
import type { PipelineEventPayload } from '../api/client'

const STAGE_LABEL: Record<string, string> = {
  started: 'Pipeline started',
  diff_analyzed: 'Diff analyzed',
  context_retrieved: 'Context retrieved',
  scenarios_generated: 'Scenarios generated',
  code_generated: 'Code generated',
  tests_running: 'Tests running',
  healing: 'Self-healing',
  completed: 'Completed',
  failed: 'Failed',
}

const STAGE_ORDER = [
  'started', 'diff_analyzed', 'context_retrieved', 'scenarios_generated',
  'code_generated', 'tests_running', 'healing', 'completed',
]

function stepStatus(stage: string, activeStage: string | null, isDone: boolean) {
  if (!activeStage) return 'pending'
  const idx = STAGE_ORDER.indexOf(stage)
  const activeIdx = STAGE_ORDER.indexOf(activeStage)
  if (activeStage === 'failed' && stage === activeStage) return 'failed'
  if (isDone && stage === 'completed') return 'done'
  if (idx < activeIdx) return 'done'
  if (idx === activeIdx) return 'active'
  return 'pending'
}

interface Props {
  events: PipelineEventPayload[]
  activeStage: string | null
  isDone: boolean
}

export function PipelineProgress({ events, activeStage, isDone }: Props) {
  return (
    <Flex direction="column" gap="2">
      {STAGE_ORDER.map(stage => {
        const status = stepStatus(stage, activeStage, isDone)
        const event = events.findLast(e => e.stage === stage)

        return (
          <div key={stage} className={`pipeline-step ${status}`}>
            <div className={`step-dot ${status}`} />
            <Box style={{ flex: 1 }}>
              <Flex align="center" justify="between">
                <Text size="2" weight="medium" style={{ color: status === 'pending' ? '#334155' : '#c7d2fe' }}>
                  {STAGE_LABEL[stage]}
                </Text>
                {status === 'active' && <div className="spinner" />}
                {status === 'done' && <Text size="1" style={{ color: '#10b981' }}>✓</Text>}
                {status === 'failed' && <Text size="1" style={{ color: '#ef4444' }}>✗</Text>}
              </Flex>
              {event && (
                <Text size="1" style={{ color: '#64748b', marginTop: 2, display: 'block' }}>{event.message}</Text>
              )}
              {event?.payload && typeof event.payload === 'object' && 'count' in event.payload && (
                <Badge size="1" variant="soft" style={{ marginTop: 4, background: 'rgba(99,102,241,0.12)', color: '#a5b4fc' }}>
                  {String(event.payload['count'])} item{Number(event.payload['count']) !== 1 ? 's' : ''}
                </Badge>
              )}
            </Box>
          </div>
        )
      })}
    </Flex>
  )
}
