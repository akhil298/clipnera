/** Query keys for the editor. One file per domain in lib/query/keys/; see docs/revamp/wave6/01-platform-api.md. */
export const editorKeys = {
  all: ['editor'] as const,
  projects: () => [...editorKeys.all, 'projects'] as const,
  /** The last server-acked snapshot; the live document is owned by the doc store (frontend.md §3.4). staleTime Infinity. */
  project: (id: string) => [...editorKeys.all, 'project', id] as const,
  versions: (id: string, bookmarked = false) => [...editorKeys.project(id), 'versions', bookmarked ? 'bookmarked' : 'all'] as const,
  version: (id: string, versionId: string) => [...editorKeys.project(id), 'version', versionId] as const,
  compare: (id: string, from: string, to: string) => [...editorKeys.project(id), 'compare', from, to] as const,
  runs: (id: string) => [...editorKeys.project(id), 'runs'] as const,
  activity: (id: string) => [...editorKeys.project(id), 'activity'] as const,
  estimate: (id: string, mode: string, prompt: string, chips: string) => [...editorKeys.project(id), 'estimate', mode, prompt, chips] as const,
  transcript: (id: string) => [...editorKeys.project(id), 'transcript'] as const,
  /** Signed proxy URLs; refetched when one expires (frontend.md §5.4). */
  assets: (id: string) => [...editorKeys.project(id), 'assets'] as const,
  run: (runId: string) => [...editorKeys.all, 'run', runId] as const,
};
