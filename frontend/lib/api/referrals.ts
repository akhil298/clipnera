import type { InvitedByResponse, MyReferralsResponse, ValidateCodeResponse } from '@/lib/types';

import { apiFetch } from './client';

/** Referrals from the referrer's and the invitee's side. Types mirror backend/referral/schema.py (kept in lib/types.ts). */

/** `GET /referrals/me`: the caller's code, link, rules, stats and everyone they invited. */
export const getMyReferrals = (signal?: AbortSignal) => apiFetch<MyReferralsResponse>('/referrals/me', { signal });

/** `GET /referrals/invited-by`: the referral the caller joined through, or null. */
export const getInvitedBy = (signal?: AbortSignal) => apiFetch<InvitedByResponse | null>('/referrals/invited-by', { signal });

/** `GET /referrals/validate/{code}`: whether a code can be used, and what it earns. */
export const validateReferralCode = (code: string, signal?: AbortSignal) =>
  apiFetch<ValidateCodeResponse>(`/referrals/validate/${encodeURIComponent(code)}`, { signal });
