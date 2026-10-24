'use client';

import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { isAuthenticated } from '@/lib/auth';
import { Navbar } from './Navbar';
import { SignInModal } from './SignInModal';
import { HeroSection } from './HeroSection';
import { ResultsWall } from './ResultsWall';
import { ProblemSection } from './ProblemSection';
import { OfferingsSection } from './OfferingsSection';
import { StepsSection } from './StepsSection';
import { CaptionTypographyShowcase } from './CaptionTypographyShowcase';
import { PricingSection } from './PricingSection';
import { FaqSection } from './FaqSection';
import { BottomCta } from './BottomCta';
import { Footer } from './Footer';

const FAQS = [
  {
    q: 'How does Clipnera pick the moments?',
    a: 'It transcribes your video word by word, then reads the transcript for strong hooks, emotional turns, useful takeaways and quotable lines. Each clip gets a score out of 100 and a short reason, so you can choose what to post first.',
  },
  {
    q: 'Does the score predict views?',
    a: 'No. The score helps you rank your own moments against each other. Views depend on your audience, timing and platform.',
  },
  {
    q: 'What does background noise reduction do?',
    a: 'It reduces steady background noise such as fan or air-conditioner hum, electrical hum and room echo, and evens out voice tone. It works best on constant noise; it cannot fully remove loud or overlapping sounds.',
  },
  {
    q: 'Which languages work?',
    a: 'Captions in English, Hindi, Telugu, Hinglish and Tenglish. In the editor you can write what you want in English or Hinglish.',
  },
  {
    q: 'Can I customize font styles, colors, and auto-emojis for captions?',
    a: 'Yes. Pick a caption preset, then adjust colors, uppercase text and line count, and turn automatic emojis on or off. Creating and editing brand kits with your own colors and logo is part of Pro.',
  },
  {
    q: 'Which social platforms can I publish to?',
    a: 'You can download clips for any platform, or publish directly to TikTok, YouTube Shorts and Instagram Reels. Scheduling posts and publishing to X are part of Pro. Captions and hashtags are suggested by AI, and you can edit them before posting.',
  },
  {
    q: 'Is the music safe to post?',
    a: 'Yes. Music and B-roll come from libraries licensed for commercial use, and each export lists any credit a track needs.',
  },
  {
    q: 'Does Pro renew automatically?',
    a: 'No. Pro does not renew on its own, and one-time credit packs never expire.',
  },
];

export default function LandingPageView() {
  const router = useRouter();
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [heroUrl, setHeroUrl] = useState('');
  // Only one reel plays with sound at a time.
  const [soundId, setSoundId] = useState<string | null>(null);
  const toggleSound = useCallback((id: string) => setSoundId((current) => (current === id ? null : id)), []);

  const closeAuthModal = useCallback(() => setIsAuthModalOpen(false), []);

  // Signed-out visitors sign in first; the dashboard would only bounce them back here.
  const handleLaunchStudio = () => {
    if (isAuthenticated()) router.push('/dashboard');
    else setIsAuthModalOpen(true);
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 font-['Plus_Jakarta_Sans',sans-serif]">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[70] focus:px-4 focus:py-2 focus:rounded-lg focus:bg-amber-500 focus:text-neutral-950 focus:text-xs focus:font-bold"
      >
        Skip to content
      </a>
      <SignInModal open={isAuthModalOpen} onClose={closeAuthModal} />

      <Navbar onOpenAuthModal={() => setIsAuthModalOpen(true)} onLaunchStudio={handleLaunchStudio} />

      <main id="main">
        <HeroSection
          heroUrl={heroUrl}
          setHeroUrl={setHeroUrl}
          onLaunchStudio={handleLaunchStudio}
          soundId={soundId}
          toggleSound={toggleSound}
        />
        <ResultsWall soundId={soundId} toggleSound={toggleSound} />
        <ProblemSection />
        <OfferingsSection />
        <StepsSection onLaunchStudio={handleLaunchStudio} />
        <CaptionTypographyShowcase />
        <PricingSection onLaunchStudio={handleLaunchStudio} />
        <FaqSection faqs={FAQS} />
        <BottomCta heroUrl={heroUrl} setHeroUrl={setHeroUrl} onLaunchStudio={handleLaunchStudio} />
      </main>

      <Footer onLaunchApp={handleLaunchStudio} onOpenAuthModal={() => setIsAuthModalOpen(true)} />
    </div>
  );
}
