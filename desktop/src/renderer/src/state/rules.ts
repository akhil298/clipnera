import type { StylePreference } from '../../../shared/api'
import { project } from './project'
import { createStore } from './store'

/** The open project's Edit Rules, and what the AI has learned from the person's corrections. */
export const rules = createStore<{ list: string[]; learned: StylePreference[] }>({ list: [], learned: [] })

/** Reloads both whenever another project opens. Returns an unsubscribe function. */
export function connectRules(): () => void {
  let open: string | null = null
  const follow = () => {
    const id = project.get().project?.id ?? null
    if (id === open) return
    open = id
    rules.set({ list: [], learned: [] })
    if (!id) return
    void window.clipnera.project.rules().then((list) => open === id && rules.set({ list })).catch(() => undefined)
    void window.clipnera.project.style().then((learned) => open === id && rules.set({ learned })).catch(() => undefined)
  }
  follow()
  return project.subscribe(follow)
}
