/** Query keys for the brand kit and channel intro. One file per domain; see docs/revamp/wave6/01-platform-api.md. */
export const brandKeys = {
  all: ['brand'] as const,
  /** `GET /brand-kits/me`. */
  kit: () => [...brandKeys.all, 'kit'] as const,
};
