import type { AuthState } from '../../../shared/ipc'
import { createStore } from './store'

export const auth = createStore<{ state: AuthState }>({ state: { status: 'loading' } })

/** Mirrors the main process's sign-in state. Returns an unsubscribe function. */
export function connectAuth(): () => void {
  const off = window.clipnera.auth.onChange((state) => auth.set({ state }))
  void window.clipnera.auth.get().then((state) => {
    if (auth.get().state.status === 'loading') auth.set({ state })
  })
  return off
}
