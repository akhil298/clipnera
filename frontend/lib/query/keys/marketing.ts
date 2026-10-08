/** Query keys for the public marketing pages. One file per domain; see docs/revamp/wave6/01-platform-api.md. */
export const marketingKeys = {
  all: ['marketing'] as const,
  /** `GET /subscription/plans`, public. */
  plans: () => [...marketingKeys.all, 'plans'] as const,
};
