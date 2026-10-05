/** Query keys for the signed-in account (app shell). One file per domain; see docs/revamp/wave6/01-platform-api.md. */
export const accountKeys = {
  all: ['account'] as const,
  /** `GET /me`. Invalidate after anything that changes the profile, plan or credits. */
  me: () => [...accountKeys.all, 'me'] as const,
  workspaces: () => [...accountKeys.all, 'workspaces'] as const,
  /** The sidebar's Recent list and the ⌘K project rows. */
  recentProjects: () => [...accountKeys.all, 'recent-projects'] as const,
};
