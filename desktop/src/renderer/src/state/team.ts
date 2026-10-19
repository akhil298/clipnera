import type { PlanCardStep } from '../../../shared/agent'

/** Who does which plan step (brain/plan_ir.py StepKind), so a plan reads as a team at work. */
export const TEAM = ['Editor', 'Text', 'Sound', 'Look & motion'] as const
export type Member = (typeof TEAM)[number]

const BY_KIND: Record<string, Member> = {
  structure: 'Editor', tighten: 'Editor', beat_sync: 'Editor',
  title: 'Text', callouts: 'Text', captions: 'Text',
  music: 'Sound', sfx: 'Sound',
  look: 'Look & motion', zoom: 'Look & motion', reframe: 'Look & motion', transitions: 'Look & motion', flash: 'Look & motion'
}

export interface TeamLane {
  member: Member
  steps: PlanCardStep[]
  done: number
  /** working: a step is running · done: all finished · failed: one failed · waiting: not started */
  state: 'working' | 'done' | 'failed' | 'waiting'
}

export function teamOf(steps: readonly PlanCardStep[]): TeamLane[] {
  return TEAM.map((member) => {
    const mine = steps.filter((s) => s.enabled && (BY_KIND[s.kind] ?? 'Editor') === member)
    const done = mine.filter((s) => s.status === 'done' || s.status === 'skipped').length
    const state = mine.some((s) => s.status === 'running') ? 'working' : mine.some((s) => s.status === 'failed') ? 'failed' : done === mine.length ? 'done' : 'waiting'
    return { member, steps: mine, done, state } as TeamLane
  }).filter((lane) => lane.steps.length > 0)
}
