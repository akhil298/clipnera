import type { Take } from '../../../shared/takes'
import { project } from './project'
import { createStore } from './store'

export const takes = createStore<{ list: Take[] }>({ list: [] })

/** Reloads the Takes whenever another project opens. */
export function connectTakes(): () => void {
  let open: string | null = null
  const follow = () => {
    const id = project.get().project?.id ?? null
    if (id === open) return
    open = id
    takes.set({ list: [] })
    if (id) void window.clipnera.project.takes().then((list) => open === id && takes.set({ list })).catch(() => undefined)
  }
  follow()
  return project.subscribe(follow)
}
