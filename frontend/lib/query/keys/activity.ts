/** Query keys for the header activity indicator. One file per domain; see docs/revamp/wave6/01-platform-api.md. */
export const activityKeys = {
  all: ['activity'] as const,
  /** Live run state of the projects that are working right now (sorted ids, so order never splits the cache). */
  active: (projectIds: readonly string[]) => [...activityKeys.all, 'active', [...projectIds].sort().join(',')] as const,
};
