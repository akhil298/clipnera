/** Query keys for the New video flow. Shape: [domain, scope, ...params] (wave6/01-platform-api.md). */
export const uploadKeys = {
  all: ['upload'] as const,
  /** `GET /creator-intro`, read to offer the channel intro before a run. */
  creatorIntro: () => [...uploadKeys.all, 'creator-intro'] as const,
};
