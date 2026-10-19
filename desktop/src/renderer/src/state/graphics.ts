import type { LibraryGraphic } from '../../../shared/api'
import { createStore } from './store'

/** The animated graphics shelf, by id, for the viewer to draw the graphic items the AI places. */
export const graphics = createStore<{ byId: Record<string, LibraryGraphic> }>({ byId: {} })

let loading: Promise<void> | null = null

export function loadGraphics(): Promise<void> {
  loading ??= window.clipnera.project
    .graphics()
    .then((list) => graphics.set({ byId: Object.fromEntries(list.map((g) => [g.id, g])) }))
    .catch(() => {
      loading = null
    })
  return loading
}
