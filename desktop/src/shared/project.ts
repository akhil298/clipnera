import type { Timeline } from '@timeline'
import type { CaptionStyleOption, LookOption, MediaAnalysisResponse, ProjectPreview } from './api'

/** The open project as the renderer sees it. */
export interface ProjectSnapshot {
  id: string
  title: string
  version: number
  timeline: Timeline
  /** Asset id → signed URL, for footage that isn't on this Mac (added by the AI or another device). */
  assetUrls: Record<string, string>
}

export interface ProjectState {
  project: ProjectSnapshot | null
  /** Edits sent but not yet confirmed. */
  saving: boolean
  loading: boolean
  error: string | null
  /** How far the AI has got understanding each asset, by asset id. */
  analysis: Record<string, MediaAnalysisResponse>
  /** What the export will draw over the picture (captions, titles, sound cues), for the viewer. */
  preview: ProjectPreview | null
  /** The caption styles to pick from. */
  captionStyles: CaptionStyleOption[]
  /** The colour looks to pick from. */
  looks: LookOption[]
}
