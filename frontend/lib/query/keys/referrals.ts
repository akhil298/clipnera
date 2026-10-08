/** Query keys for referrals and the welcome form. One file per domain; see docs/revamp/wave6/01-platform-api.md. */
export const referralKeys = {
  all: ['referrals'] as const,
  mine: () => [...referralKeys.all, 'mine'] as const,
  invitedBy: () => [...referralKeys.all, 'invited-by'] as const,
  validate: (code: string) => [...referralKeys.all, 'validate', code] as const,
  /** `GET /onboarding`: whether the welcome form may take a code. */
  onboarding: () => [...referralKeys.all, 'onboarding'] as const,
};
