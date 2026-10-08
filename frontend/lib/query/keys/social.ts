/** Query keys for connected social channels. One file per domain; see docs/revamp/wave6/01-platform-api.md. */
export const socialKeys = {
  all: ['social'] as const,
  /** `GET /social/connections`: platforms, accounts and plan limits. */
  connections: () => [...socialKeys.all, 'connections'] as const,
};
