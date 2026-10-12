/**
 * What the Editor home hands the studio when it opens a new project: the files dropped there
 * and the first prompt. Kept in memory, because File objects can't ride in a URL.
 */

export interface StudioHandoff {
  projectId: string;
  files: File[];
  prompt: string;
}

let pending: StudioHandoff | null = null;

export function setStudioHandoff(handoff: StudioHandoff): void {
  pending = handoff;
}

/** The handoff for this project, once. */
export function takeStudioHandoff(projectId: string): StudioHandoff | null {
  if (pending?.projectId !== projectId) return null;
  const handoff = pending;
  pending = null;
  return handoff;
}
