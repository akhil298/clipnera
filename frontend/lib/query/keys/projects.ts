/** Query keys for projects and folders. One file per domain in lib/query/keys/; see docs/revamp/wave6/01-platform-api.md. */
export const projectKeys = {
  all: ['projects'] as const,
  /** The whole list; search, sort and view are filtered on the client, so they are not part of the key. */
  list: () => [...projectKeys.all, 'list'] as const,
  detail: (id: string) => [...projectKeys.all, 'detail', id] as const,
  /** Latest run state for a set of projects (sorted ids, so order never splits the cache). */
  statuses: (ids: readonly string[]) => [...projectKeys.all, 'statuses', [...ids].sort().join(',')] as const,
  folders: () => [...projectKeys.all, 'folders'] as const,
};
