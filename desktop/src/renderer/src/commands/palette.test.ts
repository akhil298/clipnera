import { describe, expect, it } from 'vitest'
import type { Command } from './registry'
import { score, search } from './palette'

const cmd = (id: string, title: string, category = 'Edit', needsArgs = false): Command<unknown> => ({ id, title, category, description: '', aiCanRun: true, needsArgs, run: () => {} })
const all = [cmd('timeline.split', 'Split at Playhead'), cmd('timeline.delete', 'Delete'), cmd('player.togglePlay', 'Play / Pause', 'Playback'), cmd('player.seek', 'Move Playhead', 'Playback', true)]

describe('command palette search', () => {
  it('matches letters in order and ranks word starts first', () => {
    expect(score('spl', all[0])).toBeGreaterThan(0)
    expect(score('xyz', all[0])).toBe(-1)
    expect(search(all, 'pl').map((c) => c.id)[0]).toBe('player.togglePlay')
    expect(search(all, 'split').map((c) => c.id)).toEqual(['timeline.split'])
  })

  it('searches categories and ids too', () => {
    expect(search(all, 'playback').map((c) => c.id)).toEqual(['player.togglePlay'])
    expect(search(all, 'timeline.del').map((c) => c.id)).toEqual(['timeline.delete'])
  })

  it('lists everything runnable for an empty query and hides commands that need arguments', () => {
    expect(search(all, '').map((c) => c.id)).toEqual(['timeline.delete', 'player.togglePlay', 'timeline.split'])
  })
})
