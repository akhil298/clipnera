import type { Timeline } from '@timeline'

/** A saved version of the edit, kept on this Mac. */
export interface Take {
  id: string
  name: string
  /** ISO time it was saved. */
  savedAt: string
  /** manual: the person saved it · auto: saved before an AI request */
  source: 'manual' | 'auto'
  timeline: Timeline
}
