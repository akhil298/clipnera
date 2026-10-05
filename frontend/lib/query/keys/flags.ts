/** Query keys for the flags bootstrap. One file per domain in lib/query/keys/; see docs/revamp/wave6/01-platform-api.md. */
export const flagKeys = {
  all: ['flags'] as const,
  /** Per subject, so a user switch in the same tab never reads the previous user's flags. */
  bootstrap: (subject: string) => [...flagKeys.all, 'bootstrap', subject] as const,
};
