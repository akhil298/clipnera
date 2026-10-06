'use client';

import { useEffect, useState } from 'react';
import { Check, Loader2 } from 'lucide-react';
import { onboardingApi, referralApi } from '@/lib/api';
import { clearPendingReferralCode, pendingReferralCode } from '@/lib/referral';
import {
  ONBOARDING_ROLES,
  ONBOARDING_SOURCES,
  type OnboardingRole,
  type OnboardingSource,
  type ValidateCodeResponse,
} from '@/lib/types';

interface WelcomeFormProps {
  onDone: () => void;
}

type Choice<T extends string> = { value: T; label: string };

function Chips<T extends string>({ options, selected, onSelect }: { options: readonly Choice<T>[]; selected: T | null; onSelect: (value: T) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={selected === option.value}
          onClick={() => onSelect(option.value)}
          className={`px-3.5 py-2 rounded-full border text-sm font-semibold transition-colors ${
            selected === option.value
              ? 'border-amber-500 bg-amber-500/10 text-amber-300'
              : 'border-neutral-800 bg-neutral-950 text-neutral-400 hover:border-neutral-700 hover:text-neutral-200'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function OtherField({ id, label, value, onChange }: { id: string; label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-xs font-semibold text-neutral-400">{label}</label>
      <input
        id={id}
        value={value}
        maxLength={80}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-white text-sm focus:border-amber-500 focus:outline-none"
      />
    </div>
  );
}

/**
 * The one-time welcome form, shown instead of the dashboard until it is done:
 * what the person does, how they heard about Clipnera and, for a new enough
 * account, a referral code (filled in from a referral link).
 */
export function WelcomeForm({ onDone }: WelcomeFormProps) {
  const [step, setStep] = useState(1);
  const [role, setRole] = useState<OnboardingRole | null>(null);
  const [roleOther, setRoleOther] = useState('');
  const [source, setSource] = useState<OnboardingSource | null>(null);
  const [sourceOther, setSourceOther] = useState('');
  const [canUseCode, setCanUseCode] = useState(false);
  const [code, setCode] = useState('');
  const [check, setCheck] = useState<ValidateCodeResponse | null>(null);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    onboardingApi
      .status()
      .then((status) => {
        setCanUseCode(status.can_use_referral_code);
        if (status.can_use_referral_code) setCode(pendingReferralCode());
      })
      .catch(() => setCanUseCode(false));
  }, []);

  // Check the code as it is typed, after a pause.
  useEffect(() => {
    const trimmed = code.trim();
    setCheck(null);
    if (!trimmed) return;
    setChecking(true);
    const timer = window.setTimeout(() => {
      referralApi
        .validate(trimmed)
        .then(setCheck)
        .catch(() => setCheck(null))
        .finally(() => setChecking(false));
    }, 400);
    return () => window.clearTimeout(timer);
  }, [code]);

  const lastStep = canUseCode ? 3 : 2;
  const stepReady =
    step === 1
      ? role !== null && (role !== 'other' || roleOther.trim() !== '')
      : step === 2
        ? source !== null && (source !== 'other' || sourceOther.trim() !== '')
        : !code.trim() || (check?.valid === true && !checking);

  const submit = async (withCode: boolean) => {
    if (!role || !source) return;
    setSaving(true);
    setError(null);
    try {
      await onboardingApi.complete({
        role,
        role_other: role === 'other' ? roleOther.trim() : null,
        heard_from: source,
        heard_from_other: source === 'other' ? sourceOther.trim() : null,
        referral_code: withCode && code.trim() ? code.trim() : null,
      });
      clearPendingReferralCode();
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save. Please try again.');
      setSaving(false);
    }
  };

  const next = () => (step < lastStep ? setStep(step + 1) : void submit(true));

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10 bg-neutral-950">
      <div className="w-full max-w-xl rounded-2xl bg-neutral-900 border border-neutral-800 p-6 sm:p-8 space-y-5 shadow-xl">
        <div className="flex gap-1.5" aria-hidden="true">
          {Array.from({ length: lastStep }, (_, i) => (
            <span key={i} className={`h-[3px] flex-1 rounded-full ${i < step ? 'bg-amber-500' : 'bg-neutral-800'}`} />
          ))}
        </div>
        <p className="text-[11px] font-semibold uppercase tracking-wider text-neutral-500">
          Step {step} of {lastStep}{step === 3 ? ' · optional' : ''}
        </p>

        {step === 1 && (
          <div className="space-y-4">
            <h1 className="font-syne text-2xl font-bold text-white">What best describes you?</h1>
            <Chips options={ONBOARDING_ROLES} selected={role} onSelect={setRole} />
            {role === 'other' && <OtherField id="role-other" label="Tell us what you do" value={roleOther} onChange={setRoleOther} />}
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <h1 className="font-syne text-2xl font-bold text-white">How did you hear about us?</h1>
            <Chips options={ONBOARDING_SOURCES} selected={source} onSelect={setSource} />
            {source === 'other' && (
              <OtherField id="source-other" label="Where did you hear about us?" value={sourceOther} onChange={setSourceOther} />
            )}
          </div>
        )}

        {step === 3 && (
          <div className="space-y-3">
            <h1 className="font-syne text-2xl font-bold text-white">Have a referral code?</h1>
            <div className="space-y-1.5">
              <label htmlFor="referral-code" className="text-xs font-semibold text-neutral-400">Referral code</label>
              <input
                id="referral-code"
                value={code}
                maxLength={32}
                autoComplete="off"
                placeholder="CLIP-XXXXX"
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                className="w-full px-3 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-white font-jetbrains tracking-wider focus:border-amber-500 focus:outline-none"
              />
            </div>
            <p className="min-h-[18px] text-xs font-semibold" aria-live="polite">
              {checking && <span className="inline-flex items-center gap-1.5 text-neutral-500"><Loader2 className="w-3 h-3 animate-spin" /> Checking…</span>}
              {!checking && check?.valid && (
                <span className="inline-flex items-center gap-1.5 text-emerald-400"><Check className="w-3.5 h-3.5" /> Invited by {check.referrer_name}</span>
              )}
              {!checking && check && !check.valid && <span className="text-rose-400">{check.reason}</span>}
            </p>
            {check?.valid && <OfferNote check={check} />}
          </div>
        )}

        {error && <p className="text-sm text-rose-400">{error}</p>}

        <div className="flex items-center justify-between gap-3 pt-1">
          {step > 1 ? (
            <button type="button" onClick={() => setStep(step - 1)} className="px-3 py-2 text-sm font-semibold text-neutral-400 hover:text-white">
              Back
            </button>
          ) : <span />}
          <div className="flex items-center gap-2">
            {step === 3 && (
              <button type="button" disabled={saving} onClick={() => void submit(false)} className="px-3 py-2 text-sm font-semibold text-neutral-400 hover:text-white">
                Skip
              </button>
            )}
            <button
              type="button"
              disabled={!stepReady || saving}
              onClick={next}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-sm font-bold disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              {step === lastStep ? 'Finish' : 'Continue'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/** What joining with this code earns, under the current rules. */
function OfferNote({ check }: { check: ValidateCodeResponse }) {
  return (
    <div className="rounded-xl border border-amber-500/25 bg-amber-500/10 px-3.5 py-3 text-sm text-amber-100">
      Buy Pro within <b>{check.pro_window_hours} hours</b> of signing up and you get <b>{check.bonus_credits} bonus credits</b>.
      They expire {check.bonus_expiry_days} days after you get them.
    </div>
  );
}
