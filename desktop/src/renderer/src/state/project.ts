import { applyOps, type Timeline, type TimelineOp } from '@timeline'
import { CACHE_FILES, MEDIA_SCHEME } from '../../../shared/media'
import type { ProjectSnapshot, ProjectState } from '../../../shared/project'
import { media } from './media'
import { createStore } from './store'

interface ProjectView extends ProjectState {
  /** The timeline with edits that are still on their way to the backend already applied. */
  timeline: Timeline | null
}

export const project = createStore<ProjectView>({ project: null, saving: false, loading: true, error: null, analysis: {}, preview: null, captionStyles: [], looks: [], timeline: null })

let pending = 0
let optimistic: Timeline | null = null
let waiting: (() => void)[] = []

/** Resolves once every edit sent so far has been confirmed (or refused). */
export function settled(): Promise<void> {
  return pending === 0 ? Promise.resolve() : new Promise((resolve) => waiting.push(resolve))
}

function show(state: ProjectState): void {
  project.set({ ...state, timeline: optimistic ?? state.project?.timeline ?? null })
}

/** Mirrors the main process's project. Returns an unsubscribe function. */
export function connectProject(): () => void {
  const off = window.clipnera.project.onChange(show)
  void window.clipnera.project.get().then(show)
  return off
}

/**
 * Applies edits at once in the UI (with the same applyOps the backend runs, so a bad edit
 * fails here before anything is sent) and then sends them. Once nothing is in flight the
 * backend's copy is shown again, so the screen always ends up matching it.
 */
export async function edit(ops: TimelineOp[]): Promise<ProjectSnapshot> {
  const current = project.get().timeline
  if (!current) throw new Error('No project is open')
  if (!ops.length) throw new Error('Nothing to change here')
  optimistic = applyOps(current, ops)
  pending++
  project.set({ timeline: optimistic })
  return track(window.clipnera.project.apply(ops))
}

/** Undo, redo and refresh change the project on the backend; show its result. */
export function sync(run: () => Promise<ProjectSnapshot>): Promise<ProjectSnapshot> {
  pending++
  return track(run())
}

async function track(request: Promise<ProjectSnapshot>): Promise<ProjectSnapshot> {
  let result: ProjectSnapshot | null = null
  try {
    result = await request
    return result
  } finally {
    pending--
    if (pending === 0) {
      optimistic = null
      // The reply and the change broadcast can arrive in either order; keep the newer.
      const shown = project.get().project
      const latest = result && (!shown || result.version >= shown.version) ? result : shown
      project.set({ project: latest, timeline: latest?.timeline ?? null })
      waiting.forEach((resolve) => resolve())
      waiting = []
    }
  }
}

/** Footage on this Mac plays from its editing copy; anything else from the backend's signed URL. */
export function assetUrl(assetId: string): string | null {
  const local = media.get().items.find((i) => i.id === assetId)
  if (local && (local.status === 'ready' || local.status === 'uploading')) {
    return `${MEDIA_SCHEME}://${local.id}/${local.kind === 'audio' ? CACHE_FILES.audioProxy : CACHE_FILES.proxy}`
  }
  return project.get().project?.assetUrls[assetId] ?? null
}
