import { beforeEach, describe, expect, it } from 'vitest'
import type { PlanCard } from '../../../shared/agent'
import type { AgentMessage } from '../../../shared/ipc'
import { chat, reduce, startTurn } from './chat'

const agent = (message: unknown) => ({ source: 'agent', message }) as AgentMessage
const plan = (status: PlanCard['status']): PlanCard => ({
  id: 'plan-1', status, title: 'Full edit', summary: 'Tighten and caption', result_line: '11:38', credits: 4, credits_charged: 0,
  steps: [{ id: 's1', kind: 'tighten', intent: 'Cut pauses', why: '', enabled: true, optional: false, status: 'pending', credits: 2, depends_on: [], note: '', undo_step_id: null }],
  assumptions: [], warnings: [], premium: [], ghost: [], outline: [], fps: 30, runner_up_title: null, error: null
})

const run = (...messages: AgentMessage[]) => messages.forEach((m) => chat.set(reduce(chat.get(), m)))
const turn = () => chat.get().turns.at(-1)!

describe('chat', () => {
  beforeEach(() => {
    chat.set({ turns: [], running: false, touched: [] })
    startTurn('Remove the pauses')
  })

  it('collects what the agent says, the tools it runs and its edits', () => {
    run(
      agent({ event: 'tool', data: { id: 't1', name: 'get_silences', label: 'Finding pauses' } }),
      agent({ event: 'tool_done', data: { id: 't1', ok: true, error: null } }),
      agent({ event: 'edit', data: { label: 'Cut 4 pauses', version: 3, undo_step_id: 'turn-1' } }),
      agent({ event: 'text', data: { text: 'I cut 4 pauses (−9 s).' } }),
      agent({ event: 'done', data: { reason: 'answered', message: null } })
    )
    expect(turn()).toMatchObject({
      status: 'done',
      note: null,
      text: ['I cut 4 pauses (−9 s).'],
      tools: [{ label: 'Finding pauses', status: 'ok' }],
      edits: [{ label: 'Cut 4 pauses', undoStepId: 'turn-1', undone: false }]
    })
  })

  it('marks an edit undone wherever it is', () => {
    run(agent({ event: 'edit', data: { label: 'Cut', version: 3, undo_step_id: 'x' } }), agent({ event: 'undone', data: { undo_step_id: 'x', version: 4 } }))
    expect(turn().edits[0].undone).toBe(true)
  })

  it('follows a plan through its steps to the end', () => {
    run(agent({ event: 'plan', data: plan('proposed') }), agent({ event: 'done', data: { reason: 'handed_over', message: null } }))
    run({ source: 'plan', planId: 'plan-1', message: { event: 'plan.updated', data: plan('running') } })
    run({ source: 'plan', planId: 'plan-1', message: { event: 'agent.step', data: { step_id: 's1', status: 'done', note: 'Cut 4 pauses' } } })
    run({ source: 'plan', planId: 'plan-1', message: { event: 'op.applied', data: { version: 5, cursor: { author: 'agent:tighten', items: ['c1'] } } } })
    expect(turn().plan?.steps[0]).toMatchObject({ status: 'done', note: 'Cut 4 pauses' })
    expect(chat.get().touched).toEqual(['c1'])
    run({ source: 'plan', planId: 'plan-1', message: { event: 'done', data: { status: 'done' } } })
    expect(turn().plan?.status).toBe('done')
    expect(chat.get().running).toBe(false)
  })

  it('records stops, failures, questions and why a turn ended early', () => {
    run({ source: 'app', message: { event: 'stopped' } })
    expect(turn()).toMatchObject({ status: 'stopped' })
    startTurn('Make it punchy')
    run(agent({ event: 'ask', data: { question: 'Which part?', options: ['Intro', 'All'] } }), agent({ event: 'done', data: { reason: 'budget', message: 'I ran out of budget.' } }))
    expect(turn()).toMatchObject({ ask: { options: ['Intro', 'All'] }, note: 'I ran out of budget.' })
    startTurn('Again')
    run({ source: 'app', message: { event: 'error', data: { message: "Can't reach Clipnera." } } })
    expect(turn()).toMatchObject({ status: 'failed', note: "Can't reach Clipnera." })
  })
})

describe('when the AI is busy', () => {
  it('is free while a plan waits for approval, and busy while it runs', () => {
    startTurn('Edit the video')
    let state = chat.get()
    state = reduce(state, { source: 'agent', message: { event: 'plan', data: plan('proposed') } } as AgentMessage)
    state = reduce(state, { source: 'agent', message: { event: 'done', data: { reason: 'handed_over', message: null } } } as AgentMessage)
    expect(state.running).toBe(false)
    state = reduce(state, { source: 'plan', planId: 'plan-1', message: { event: 'plan.updated', data: plan('running') } } as AgentMessage)
    expect(state.running).toBe(true)
    state = reduce(state, { source: 'plan', planId: 'plan-1', message: { event: 'done', data: { status: 'done' } } } as AgentMessage)
    expect(state.running).toBe(false)
  })
})
