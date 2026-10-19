import type { ExportState } from '../../../shared/export'
import { createStore } from './store'

export const exporting = createStore<ExportState>({ phase: 'idle', render: null, progress: 0, file: null, error: null })

export function connectExport(): () => void {
  const off = window.clipnera.export.onChange((state) => exporting.set(state))
  void window.clipnera.export.get().then((state) => exporting.set(state))
  return off
}
