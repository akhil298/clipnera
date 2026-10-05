import type { Metadata } from 'next';

import { SignInPage, type SignInSearchParams } from '@/components/auth-v2/SignInPage';

export const metadata: Metadata = { title: 'Sign in · Clipnera' };

/** Kept for old links; the same page as /login (screens/01 §3). */
export default function Page({ searchParams }: { searchParams: SignInSearchParams }) {
  return <SignInPage searchParams={searchParams} />;
}
