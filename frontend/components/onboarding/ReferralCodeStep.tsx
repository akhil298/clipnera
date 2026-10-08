'use client';

import { Check } from 'lucide-react';

import { InlineAlert, Input, Spinner } from '@/components/ui';

import type { WelcomeForm } from './useWelcomeForm';

/** The optional referral code, prefilled from a referral link, checked as it is typed. */
export function ReferralCodeStep({ form }: { form: WelcomeForm }) {
  const { check } = form;
  return (
    <div className="flex flex-col gap-3">
      <Input
        label="Referral code"
        value={form.code}
        maxLength={32}
        autoComplete="off"
        spellCheck={false}
        placeholder="CLIP-XXXXX"
        onChange={(event) => form.setCode(event.target.value)}
        error={check && !check.valid ? (check.reason ?? 'This code can’t be used.') : undefined}
        data-autofocus
        className="font-cn-mono tracking-wider"
      />
      <p aria-live="polite" className="min-h-5 text-cn-caption">
        {form.checking && <Spinner size="sm" label="Checking…" showLabel />}
        {check?.valid && (
          <span className="inline-flex items-center gap-1.5 text-cn-success-text">
            <Check aria-hidden className="size-3.5" /> Invited by {check.referrer_name}
          </span>
        )}
      </p>
      {check?.valid && (
        <InlineAlert>
          Buy Pro within {check.pro_window_hours} hours of signing up and you get {check.bonus_credits} bonus credits. They expire{' '}
          {check.bonus_expiry_days} days after you get them.
        </InlineAlert>
      )}
    </div>
  );
}
