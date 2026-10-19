import { beforeEach, describe, expect, it } from 'vitest'
import { DEFAULT_LAYOUT, type LayoutState } from '../state/layout'
import { createStore, type Store } from '../state/store'
import { CommandRegistry } from './registry'
import { registerViewCommands } from './view'

describe('view commands', () => {
  let registry: CommandRegistry
  let layout: Store<LayoutState>

  beforeEach(() => {
    registry = new CommandRegistry()
    layout = createStore(DEFAULT_LAYOUT)
    registerViewCommands(registry, layout)
  })

  it('toggles each panel', async () => {
    await registry.execute('view.toggleBottomPanel')
    await registry.execute('view.toggleSidePanel')
    await registry.execute('view.toggleAiPanel')
    expect(layout.get()).toMatchObject({ bottomVisible: false, sideVisible: false, aiVisible: false })
  })

  it('opens a side view and shows the panel', async () => {
    layout.set({ sideVisible: false })
    await registry.execute('view.showSideView', { view: 'sounds' }, 'ai')
    expect(layout.get()).toMatchObject({ sideView: 'sounds', sideVisible: true })
  })

  it('rejects a view that does not exist', async () => {
    await expect(registry.execute('view.showSideView', { view: 'nope' }, 'ai')).rejects.toThrow(/view must be one of/)
    expect(layout.get().sideView).toBe('media')
  })

  it('keeps the AI from hiding its own panel', async () => {
    await expect(registry.execute('view.toggleAiPanel', undefined, 'ai')).rejects.toThrow(/AI can't run/)
  })

  it('gives every command a description for the AI', () => {
    for (const c of registry.list()) expect(c.description.length).toBeGreaterThan(10)
  })
})
