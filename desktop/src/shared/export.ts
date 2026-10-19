import type { RenderStatus } from './agent'

/** An export of the open project: rendered on the backend, then saved on this Mac. */
export interface ExportState {
  /** idle · rendering on the backend · downloading the finished file · saved · failed */
  phase: 'idle' | 'rendering' | 'downloading' | 'saved' | 'failed'
  render: RenderStatus | null
  /** 0–1 while downloading. */
  progress: number
  /** Where the finished video was saved. */
  file: string | null
  error: string | null
}
