import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { type MockPageProps, pickState, SCREENS } from '../_mock/states';
import { ProgressMock } from './ProgressMock';

const SCREEN = SCREENS.progress;

export const metadata: Metadata = {
  title: `${SCREEN.title} · Entry mockups · Clipnera`,
  robots: { index: false, follow: false },
};

/** Mockup: progress. Development only; spec in docs/revamp/screens/01-entry-and-dashboard.md. */
export default async function Page({ searchParams }: MockPageProps) {
  if (process.env.NODE_ENV === 'production') notFound();
  const { state, theme } = await searchParams;
  const current = pickState(SCREEN.states, state);
  // Keyed by state so each state starts fresh (sample data seeds local state).
  return <ProgressMock key={current} state={current} theme={theme} />;
}
