'use client';

import { useEffect } from 'react';
import { captureReferralCode } from '@/lib/referral';

/** Keeps the code from a referral link (/?ref=...) through Google sign-in, so
 * the welcome form can fill it in. Renders nothing. */
export function ReferralCapture() {
  useEffect(() => {
    captureReferralCode(window.location.search);
  }, []);
  return null;
}
