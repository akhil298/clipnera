import type { Metadata } from 'next';

import { SignInPage, type SignInSearchParams } from '@/components/auth-v2/SignInPage';

export const metadata: Metadata = { title: 'Sign in · Clipnera' };

export default function Page({ searchParams }: { searchParams: SignInSearchParams }) {
  return <SignInPage searchParams={searchParams} />;
}
