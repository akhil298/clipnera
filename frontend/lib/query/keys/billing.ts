/**
 * Query keys for the plan and billing page. The entitlements themselves stay under
 * `creditKeys.entitlements()` (lib/query/keys/credits.ts) so the shell, billing and
 * every plan lock share one cache entry (screens/03 §17). One file per domain.
 */
export const billingKeys = {
  all: ['billing'] as const,
  /** `GET /subscription/plans`: plans and credit packs. Changes only on deploy. */
  plans: () => [...billingKeys.all, 'plans'] as const,
  /** `GET /payments/my`: every payment the user submitted. */
  payments: () => [...billingKeys.all, 'payments'] as const,
  /** `GET /subscription/ledger?limit=`. */
  ledger: (limit: number) => [...billingKeys.all, 'ledger', limit] as const,
};
