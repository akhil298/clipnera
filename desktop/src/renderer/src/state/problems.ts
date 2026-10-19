import { findProblems, type Problem } from '../timeline/problems'
import { media } from './media'
import { assetUrl, project } from './project'
import { createStore } from './store'

export const problems = createStore<{ list: Problem[] }>({ list: [] })

/** Re-checks the edit whenever the project, its preview or the media change. */
export function connectProblems(): () => void {
  const check = () => {
    const { timeline, preview } = project.get()
    problems.set({ list: timeline ? findProblems(timeline, preview, media.get().items, (id) => assetUrl(id) !== null) : [] })
  }
  check()
  const offProject = project.subscribe(check)
  const offMedia = media.subscribe(check)
  return () => {
    offProject()
    offMedia()
  }
}
