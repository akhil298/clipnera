/** Query keys for projects' clips. One file per domain in lib/query/keys/; see docs/revamp/wave6/01-platform-api.md. */
export const clipKeys = {
  all: ['clips'] as const,
  list: (projectId: string) => [...clipKeys.all, 'list', projectId] as const,
};
