'use client';

import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { isAuthenticated } from '@/lib/auth';
import { Navbar } from './Navbar';
import { SignInModal } from './SignInModal';
import { HeroSection } from './HeroSection';
import { ClipWall } from './ClipWall';
import { EngineSection } from './EngineSection';
import { BeforeAfterShowcase } from './BeforeAfterShowcase';
import { CaptionTypographyShowcase } from './CaptionTypographyShowcase';
import { ResultsPreview } from './ResultsPreview';
import { RoiCalculator } from './RoiCalculator';
import { PublishSection } from './PublishSection';
import { PricingSection } from './PricingSection';
import { FaqSection } from './FaqSection';
import { BottomCta } from './BottomCta';
import { Footer } from './Footer';

export default function LandingPageView() {
  const router = useRouter();
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [heroUrl, setHeroUrl] = useState('');

  const faqs = [
    {
      q: 'How does the AI choose the most viral moments from long videos?',
      a: 'Clipnera transcribes your video, then AI reviews the transcript for strong hooks, emotional moments, useful takeaways and shareable lines. Each clip gets an estimated virality score out of 100. Scores help you choose; they do not predict views.',
    },
    {
      q: 'What does background noise reduction do?',
      a: 'It reduces steady background noise such as fan or air-conditioner hum, electrical hum and room echo, and evens out voice tone. It works best on constant noise; it cannot fully remove loud or overlapping sounds.',
    },
    {
      q: 'Can I customize font styles, colors, and auto-emojis for captions?',
      a: 'Yes. Pick a caption preset, then adjust colors, uppercase text and line count, and turn automatic emojis on or off. Creating and editing brand kits with your own colors and logo is part of Pro.',
    },
    {
      q: 'Which social platforms can I publish to?',
      a: 'You can download clips for any platform, or publish directly to TikTok, YouTube Shorts and Instagram Reels. Scheduling posts and publishing to X are part of Pro. Captions and hashtags are suggested by AI, and you can edit them before posting.',
    },
  ];

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
      />

      <ClipWall onLaunchStudio={handleLaunchStudio} />

      <EngineSection />

      <BeforeAfterShowcase />

      <CaptionTypographyShowcase />

      <ResultsPreview onLaunchStudio={handleLaunchStudio} />

      <RoiCalculator onLaunchStudio={handleLaunchStudio} />

      <PublishSection />

      <PricingSection onLaunchStudio={handleLaunchStudio} />

      <FaqSection faqs={faqs} />

      <BottomCta heroUrl={heroUrl} setHeroUrl={setHeroUrl} onLaunchStudio={handleLaunchStudio} />
      </main>

      <Footer onLaunchApp={handleLaunchStudio} onOpenAuthModal={() => setIsAuthModalOpen(true)} />
    </div>
  );
}
