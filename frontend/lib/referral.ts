import type { ReferralFailReason, ReferralStatus } from '@/lib/types';
import { parseApiDate } from '@/lib/utils/dates';

/** A code from a referral link (/?ref=CLIP-XXXXX), kept until the welcome form
 * uses it. It only fills in the form: the server decides whether it counts. */
const PENDING_CODE_KEY = 'clipnera_referral_code';
const CODE_PATTERN = /^(CLIP-)?[A-Z0-9]{4,10}$/;

export function captureReferralCode(search: string): void {
  const code = new URLSearchParams(search).get('ref')?.trim().toUpperCase();
  if (!code || !CODE_PATTERN.test(code)) return;
  try {
    localStorage.setItem(PENDING_CODE_KEY, code);
  } catch {
    // Storage blocked: the person can still type the code in the form.
  }
}

export function pendingReferralCode(): string {
  try {
    return localStorage.getItem(PENDING_CODE_KEY) ?? '';
  } catch {
    return '';
  }
}

export function clearPendingReferralCode(): void {
  try {
    localStorage.removeItem(PENDING_CODE_KEY);
  } catch {
    // Nothing stored.
  }
}

export const OPEN_REFERRAL_STATUSES: ReferralStatus[] = ['pending_pro', 'awaiting_approval', 'pending_video'];

export const REFERRAL_STATUS_LABELS: Record<ReferralStatus, string> = {
  pending_pro: 'Waiting for Pro',
  awaiting_approval: 'Payment awaiting approval',
  pending_video: 'Waiting for first video',
  succeeded: 'Succeeded',
  partial: 'Partly completed',
  failed: 'Failed',
  void: 'Cancelled',
};

export const REFERRAL_FAIL_LABELS: Record<ReferralFailReason, string> = {
  pro_not_bought: 'Pro not bought in time',
  payment_rejected: 'Payment rejected',
  approval_timeout: 'Payment not approved in time',
  no_video: 'No video in time',
  payment_reversed: 'Pro payment reversed',
  account_deleted: 'Account deleted',
  referrer_unavailable: 'Referrer account inactive',
  voided_by_admin: 'Cancelled after review',
};

/** "1d 7h left", "9h 04m left", or null once the time has passed. */
export function timeLeft(deadline: string | null, now: number = Date.now()): string | null {
  if (!deadline) return null;
  const ms = parseApiDate(deadline).getTime() - now;
  if (ms <= 0) return null;
  const hours = Math.floor(ms / 3_600_000);
  const minutes = Math.floor((ms % 3_600_000) / 60_000);
  if (hours >= 24) return `${Math.floor(hours / 24)}d ${hours % 24}h left`;
  return `${hours}h ${String(minutes).padStart(2, '0')}m left`;
}

/** Under this much time left, a countdown is shown as urgent. */
export const URGENT_MS = 12 * 3_600_000;

export function isUrgent(deadline: string | null, now: number = Date.now()): boolean {
  if (!deadline) return false;
  const ms = parseApiDate(deadline).getTime() - now;
  return ms > 0 && ms < URGENT_MS;
}

export function shortDate(value: string): string {
  return parseApiDate(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}
