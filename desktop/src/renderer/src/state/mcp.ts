import type { McpState } from '../../../shared/ipc'
import { createStore } from './store'

export const mcp = createStore<{ state: McpState | null; open: boolean }>({ state: null, open: false })

export function connectMcp(): () => void {
  void window.clipnera.mcp.get().then((state) => mcp.set({ state }))
  return window.clipnera.mcp.onChange((state) => mcp.set({ state }))
}
