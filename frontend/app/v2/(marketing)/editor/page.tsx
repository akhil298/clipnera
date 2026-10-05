import type { Metadata } from 'next';

import { MarketingPage } from '@/components/marketing/MarketingPage';
import { ScrollToSection } from '@/components/marketing/ScrollToSection';

export const metadata: Metadata = {
  title: 'Clipnera Editor · Change anything with a sentence',
  description: 'Drop in footage, say what you want, and edit the result on a real timeline.',
};

/** The landing, opened at its Editing section (R1, D4). */
export default function EditorLandingPage() {
  return (
    <>
      <MarketingPage />
      <ScrollToSection id="editing" />
    </>
  );
}
