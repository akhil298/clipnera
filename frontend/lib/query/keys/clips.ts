/** Query keys for projects' clips. One file per domain in lib/query/keys/; see docs/revamp/wave6/01-platform-api.md. */
export const clipKeys = {
  all: ['clips'] as const,
  /** The project row (title, source, status) until lib/api/projects.ts has a detail read. */
  project: (projectId: string) => [...clipKeys.all, 'project', projectId] as const,
  list: (projectId: string) => [...clipKeys.all, 'list', projectId] as const,
};
