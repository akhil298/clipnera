'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { X } from 'lucide-react';
import { GoogleSignIn } from '@/components/auth/GoogleSignIn';
import { isAuthenticated } from '@/lib/auth';
import { Navbar } from './Navbar';
import { HeroSection } from './HeroSection';
import { BeforeAfterShowcase } from './BeforeAfterShowcase';
import { SocialProof } from './SocialProof';
import { FeaturesGrid } from './FeaturesGrid';
import { CaptionTypographyShowcase } from './CaptionTypographyShowcase';
import { HowItWorks } from './HowItWorks';
import { RoiCalculator } from './RoiCalculator';
import { PricingSection } from './PricingSection';
import { FaqSection } from './FaqSection';
import { BottomCta } from './BottomCta';
import { Footer } from './Footer';

export default function LandingPageView() {
  const router = useRouter();
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [heroUrl, setHeroUrl] = useState('');
  const [previewCaptionPreset, setPreviewCaptionPreset] = useState<'hormozi' | 'mrbeast' | 'cyberpunk' | 'neon'>('hormozi');

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

  useEffect(() => {
    if (!isAuthModalOpen) return;
    const closeOnEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsAuthModalOpen(false);
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [isAuthModalOpen]);

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
      {isAuthModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Sign in to Clipnera"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md"
        >
          <div className="relative w-full max-w-md rounded-2xl bg-neutral-900/90 border border-neutral-800 p-6 shadow-xl">
            <button
              onClick={() => setIsAuthModalOpen(false)}
              aria-label="Close"
              autoFocus
              className="absolute top-5 right-5 p-1.5 rounded-full text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
            <GoogleSignIn />
          </div>
        </div>
      )}

      <Navbar onOpenAuthModal={() => setIsAuthModalOpen(true)} onLaunchStudio={handleLaunchStudio} />

      <main id="main">
      <HeroSection
        heroUrl={heroUrl}
        setHeroUrl={setHeroUrl}
        onLaunchStudio={handleLaunchStudio}
      />

      <BeforeAfterShowcase
        previewCaptionPreset={previewCaptionPreset}
        setPreviewCaptionPreset={setPreviewCaptionPreset}
        onLaunchStudio={handleLaunchStudio}
      />

      <SocialProof />

      <section id="features" className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-16">
          <div className="text-center max-w-3xl mx-auto space-y-3">
            <span className="text-xs font-extrabold uppercase tracking-wider text-amber-400 font-['Syne',sans-serif]">Complete Viral Production Suite</span>
            <h2 className="text-2xl sm:text-4xl font-extrabold text-white font-['Syne',sans-serif]">Everything you need to turn long videos into shorts</h2>
            <p className="text-xs sm:text-sm text-neutral-300">No manual timeline scrubbing. No complex video editing software. Clipnera handles clipping, captions and reframing, and you review the result.</p>
          </div>
          <FeaturesGrid />
          <CaptionTypographyShowcase />
        </div>
      </section>

      <HowItWorks />

      <RoiCalculator onLaunchStudio={handleLaunchStudio} />

      <PricingSection onLaunchStudio={handleLaunchStudio} />

      <FaqSection faqs={faqs} />

      <BottomCta onLaunchStudio={handleLaunchStudio} />
      </main>

      <Footer onLaunchApp={handleLaunchStudio} onOpenAuthModal={() => setIsAuthModalOpen(true)} />
    </div>
  );
}
