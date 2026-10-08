import type { DocTransport } from '@/lib/editor/store';

import { applyEditorOps, getEditorProject } from './projects';

/** The doc store's network side, on the real routes. Resync is a full GET until EB-2 (`ops?since=`) exists. */
export const editorTransport: DocTransport = {
  sendOps: (projectId, baseVersion, ops) => applyEditorOps(projectId, baseVersion, ops),
  fetchProject: async (projectId) => {
    const project = await getEditorProject(projectId);
    return { timeline: project.timeline, version: project.version };
  },
};
