/** Query keys for the in-app inbox. One file per domain in lib/query/keys/; see docs/revamp/wave6/01-platform-api.md. */
export const notificationKeys = {
  all: ['notifications'] as const,
  /** `GET /notifications`: the newest page of the inbox. */
  inbox: () => [...notificationKeys.all, 'inbox'] as const,
};
