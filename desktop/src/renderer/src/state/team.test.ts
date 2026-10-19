import { describe, expect, it } from 'vitest'
import type { PlanCardStep } from '../../../shared/agent'
import { teamOf } from './team'

const step = (id: string, kind: string, status: PlanCardStep['status'], enabled = true): PlanCardStep => ({ id, kind, intent: id, why: '', enabled, optional: false, status, credits: 1, depends_on: [], note: '', undo_step_id: null })

describe('the agent team', () => {
  it('groups plan steps by who does them, with progress', () => {
    const lanes = teamOf([step('s1', 'structure', 'done'), step('s2', 'tighten', 'running'), step('s3', 'captions', 'pending'), step('s4', 'music', 'done'), step('s5', 'zoom', 'failed'), step('s6', 'sfx', 'pending', false)])
    expect(lanes.map((l) => [l.member, l.done, l.steps.length, l.state])).toEqual([
      ['Editor', 1, 2, 'working'],
      ['Text', 0, 1, 'waiting'],
      ['Sound', 1, 1, 'done'],
      ['Look & motion', 0, 1, 'failed']
    ])
  })
})
