/** Query keys for a project's run. One file per domain in lib/query/keys/; see docs/revamp/wave6/01-platform-api.md. */
export const jobKeys = {
  all: ['jobs'] as const,
  status: (projectId: string) => [...jobKeys.all, 'status', projectId] as const,
  download: (projectId: string) => [...jobKeys.all, 'download', projectId] as const,
  credits: (projectId: string) => [...jobKeys.all, 'credits', projectId] as const,
};
