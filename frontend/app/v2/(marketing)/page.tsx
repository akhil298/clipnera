import type { Metadata } from 'next';

import { MarketingPage } from '@/components/marketing/MarketingPage';

export const metadata: Metadata = {
  title: 'Clipnera · Long video in. Shorts out.',
  description:
    'Paste a YouTube link or add a video and say what you want. Clipnera finds the moments worth posting, reframes them to 9:16, cleans the audio and adds captions.',
};

export default function LandingPage() {
  return <MarketingPage />;
}
