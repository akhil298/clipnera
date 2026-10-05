/** Home's server state. Shape: [domain, scope, ...params] (wave6/01-platform-api.md). */
export const homeKeys = {
  all: ['home'] as const,
  me: () => [...homeKeys.all, 'me'] as const,
  entitlements: () => [...homeKeys.all, 'entitlements'] as const,
  projects: () => [...homeKeys.all, 'projects'] as const,
  runStatuses: (projectIds: readonly string[]) => [...homeKeys.all, 'run-statuses', projectIds] as const,
  youtube: (url: string) => [...homeKeys.all, 'youtube', url] as const,
};
