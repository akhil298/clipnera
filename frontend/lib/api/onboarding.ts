import type { OnboardingRequest, OnboardingResponse, OnboardingStatusResponse } from '@/lib/types';

import { apiFetch } from './client';

/** The one-time welcome form. Types mirror backend/onboarding/schema.py (kept in lib/types.ts, shared with the legacy form). */

/** `GET /onboarding`: done yet, and whether the form may take a referral code. */
export const getOnboarding = (signal?: AbortSignal) => apiFetch<OnboardingStatusResponse>('/onboarding', { signal });

/** `POST /onboarding`: saves the answers once; `/me` then reports `onboarding_completed: true`. */
export const completeOnboarding = (body: OnboardingRequest) =>
  apiFetch<OnboardingResponse>('/onboarding', { method: 'POST', body });
