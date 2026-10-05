/** Query keys for the credit balance and how to top it up. One file per domain; see docs/revamp/wave6/01-platform-api.md. */
export const creditKeys = {
  all: ['credits'] as const,
  /** `GET /subscription/entitlements`: balance, plan and billing state. */
  entitlements: () => [...creditKeys.all, 'entitlements'] as const,
  /** `GET /subscription/plans` (credit packs). Changes only on deploy. */
  packs: () => [...creditKeys.all, 'packs'] as const,
  /** `GET /payments/my`: read only while a payment is being checked. */
  payments: () => [...creditKeys.all, 'payments'] as const,
};
