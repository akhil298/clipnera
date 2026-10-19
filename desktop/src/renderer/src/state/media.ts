import type { MediaItem } from '../../../shared/media'
import { createStore } from './store'

export const media = createStore<{ items: MediaItem[] }>({ items: [] })

/** Mirrors the main process's media library. Returns an unsubscribe function. */
export function connectMedia(): () => void {
  const off = window.clipnera.media.onChange((items) => media.set({ items }))
  void window.clipnera.media.list().then((items) => media.set({ items }))
  return off
}
