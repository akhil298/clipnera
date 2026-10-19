import type { ClipneraBridge } from '../shared/ipc'

declare global {
  interface Window {
    clipnera: ClipneraBridge
  }
}
