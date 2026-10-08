'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { completeOnboarding, getOnboarding } from '@/lib/api/onboarding';
import { validateReferralCode } from '@/lib/api/referrals';
import { accountKeys } from '@/lib/query/keys/account';
import { referralKeys } from '@/lib/query/keys/referrals';
import { clearPendingReferralCode, pendingReferralCode } from '@/lib/referral';
import type { OnboardingRole, OnboardingSource } from '@/lib/types';

/** Pause after typing before a code is checked. */
const CHECK_DELAY_MS = 400;

/** "Other" needs a few words, as backend/onboarding/schema.py requires. */
const answered = (choice: string | null, other: string) => choice !== null && (choice !== 'other' || other.trim() !== '');

/**
 * The one-time welcome form (backend/onboarding): what the person does, how
 * they heard about Clipnera and, for a brand-new account, a referral code
 * prefilled from a referral link. Same fields and rules as the legacy form.
 */
export function useWelcomeForm() {
  const queryClient = useQueryClient();
  const [role, setRole] = useState<OnboardingRole | null>(null);
  const [roleOther, setRoleOther] = useState('');
  const [source, setSource] = useState<OnboardingSource | null>(null);
  const [sourceOther, setSourceOther] = useState('');
  const [code, setCode] = useState('');
  const [typedCode, setTypedCode] = useState('');

  const status = useQuery({ queryKey: referralKeys.onboarding(), queryFn: ({ signal }) => getOnboarding(signal) });
  const canUseCode = status.data?.can_use_referral_code === true;

  useEffect(() => {
    if (canUseCode) setCode((current) => current || pendingReferralCode());
  }, [canUseCode]);

  // The code is checked once typing pauses.
  useEffect(() => {
    const timer = window.setTimeout(() => setTypedCode(code.trim()), CHECK_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [code]);

  const check = useQuery({
    queryKey: referralKeys.validate(typedCode),
    queryFn: ({ signal }) => validateReferralCode(typedCode, signal),
    enabled: canUseCode && typedCode !== '',
    staleTime: 60_000,
  });
  const checking = code.trim() !== typedCode || check.isFetching;

  const submit = useMutation({
    mutationFn: (withCode: boolean) =>
      completeOnboarding({
        role: role!,
        role_other: role === 'other' ? roleOther.trim() : null,
        heard_from: source!,
        heard_from_other: source === 'other' ? sourceOther.trim() : null,
        referral_code: withCode && canUseCode && code.trim() ? code.trim() : null,
      }),
    onSuccess: () => {
      clearPendingReferralCode();
      void queryClient.invalidateQueries({ queryKey: accountKeys.me() });
      void queryClient.invalidateQueries({ queryKey: referralKeys.all });
    },
  });

  return {
    role,
    setRole,
    roleOther,
    setRoleOther,
    source,
    setSource,
    sourceOther,
    setSourceOther,
    roleReady: answered(role, roleOther),
    sourceReady: answered(source, sourceOther),
    canUseCode,
    code,
    setCode: (value: string) => setCode(value.toUpperCase()),
    check: code.trim() && !checking ? check.data : undefined,
    checking: code.trim() !== '' && checking,
    /** An empty code is fine; a typed one must be valid. */
    codeReady: !code.trim() || (!checking && check.data?.valid === true),
    submit,
  };
}

export type WelcomeForm = ReturnType<typeof useWelcomeForm>;
