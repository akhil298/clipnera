'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { X } from 'lucide-react';
import { AuthForm } from '@/components/auth/AuthForm';
import { SAMPLE_PROJECTS } from '@/lib/data/mockProjects';
import { Navbar } from './Navbar';
import { HeroSection } from './HeroSection';
import { BeforeAfterShowcase } from './BeforeAfterShowcase';
import { SocialProof } from './SocialProof';
import { FeaturesGrid } from './FeaturesGrid';
import { CaptionTypographyShowcase } from './CaptionTypographyShowcase';
import { SamplesSection } from './SamplesSection';
import { HowItWorks } from './HowItWorks';
import { RoiCalculator } from './RoiCalculator';
import { PricingSection } from './PricingSection';
import { FaqSection } from './FaqSection';
import { BottomCta } from './BottomCta';
import { Footer } from './Footer';

export default function LandingPageView() {
  const router = useRouter();
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [heroUrl, setHeroUrl] = useState('https://www.youtube.com/watch?v=100m-leads-masterclass');
  const [previewCaptionPreset, setPreviewCaptionPreset] = useState<'hormozi' | 'mrbeast' | 'cyberpunk' | 'neon'>('hormozi');

  const faqs = [
    {
      q: 'How does the AI choose the most viral moments from long videos?',
      a: 'Our Gemini 3.7 Flash engine analyzes transcript density, vocal inflection pitch, narrative curiosity loops, and visual movement to detect emotional climax beats. It calculates an algorithmic Virality Score (0-100) and extracts 30-60 second clips optimized for high watch retention.',
    },
    {
      q: 'What is the AI Background Noise Removal (Studio Denoise) feature?',
      a: 'Studio Denoise uses neural speech isolation to strip away air conditioning hum, room reverb, microphone hiss, and background noise from recorded audio, outputting broadcast-grade podcast clarity without needing expensive studio microphones.',
    },
    {
      q: 'Can I customize font styles, colors, and auto-emojis for captions?',
      a: 'Absolutely. Choose from proven presets like Hormozi, MrBeast, Cyberpunk, and Neon, or customize your own Brand Kit with custom colors, custom logo watermarks, uppercase text, line counts, and animated auto-emojis.',
    },
    {
      q: 'Which social platforms are supported for 1-click scheduling?',
      a: 'You can directly export or schedule auto-posts to TikTok, YouTube Shorts, Instagram Reels, and X (Twitter), complete with AI-generated hashtags and hook optimization tags.',
    },
  ];

  useEffect(() => {
    if (localStorage.getItem('token')) {
      router.replace('/dashboard');
    }
  }, [router]);

  const handleAuthenticated = () => {
    setIsAuthModalOpen(false);
    router.replace('/dashboard');
  };

  const handleLaunchStudio = () => router.push('/dashboard');
  const handleLaunchApp = () => router.push('/dashboard');
  const handleOpenSample = (projectId: string) => router.push('/dashboard');

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 font-['Plus_Jakarta_Sans',sans-serif]">
      {isAuthModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="relative w-full max-w-md rounded-2xl bg-neutral-900/90 border border-neutral-800 p-6 shadow-xl">
            <button
              onClick={() => setIsAuthModalOpen(false)}
              className="absolute top-5 right-5 p-1.5 rounded-full text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
            <AuthForm onAuthenticated={handleAuthenticated} />
          </div>
        </div>
      )}

      <Navbar onOpenAuthModal={() => setIsAuthModalOpen(true)} onLaunchStudio={handleLaunchStudio} />

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
            <h2 className="text-2xl sm:text-4xl font-extrabold text-white font-['Syne',sans-serif]">Everything needed to 10x your short-form video reach</h2>
            <p className="text-xs sm:text-sm text-neutral-400">No manual timeline scrubbing. No complex video editing software. Clipnera automates the entire end-to-end viral clipping workflow.</p>
          </div>
          <FeaturesGrid />
          <CaptionTypographyShowcase />
        </div>
      </section>

      <SamplesSection onLaunchApp={handleLaunchApp} onOpenSample={handleOpenSample} />

      <HowItWorks />

      <RoiCalculator onLaunchStudio={handleLaunchStudio} />

      <PricingSection onLaunchStudio={handleLaunchStudio} />

      <FaqSection faqs={faqs} />

      <BottomCta onLaunchStudio={handleLaunchStudio} />

      <Footer onLaunchApp={handleLaunchApp} onOpenAuthModal={() => setIsAuthModalOpen(true)} />
    </div>
  );
}
