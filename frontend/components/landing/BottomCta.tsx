'use client';

import { LandingVideo } from './LandingVideo';
import { VideoLinkForm } from './VideoLinkForm';

interface BottomCtaProps {
  heroUrl: string;
  setHeroUrl: (url: string) => void;
  onLaunchStudio: () => void;
}

export function BottomCta({ heroUrl, setHeroUrl, onLaunchStudio }: BottomCtaProps) {
  return (
    <LandingVideo clip="host" className="relative min-h-[380px]" mediaClassName="scale-105">
      <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(10,10,10,0.95)_0%,rgba(10,10,10,0.88)_62%,rgba(10,10,10,0.5)_100%)]" />
      <section className="relative mx-auto max-w-[1440px] px-4 py-16 sm:px-8 xl:px-16">
        <div className="max-w-[1000px] space-y-6">
          <h2 className="font-syne text-[40px] font-extrabold leading-[0.98] tracking-[-0.035em] text-white sm:text-5xl lg:text-[60px]">
            Your next Shorts are
            <br />
            <span className="text-amber-500">already recorded.</span>
          </h2>
          <div className="max-w-[600px]">
            <VideoLinkForm id="cta-url" url={heroUrl} setUrl={setHeroUrl} onSubmit={onLaunchStudio} />
          </div>
          <p className="text-[13px] text-neutral-300">Free plan, no card needed.</p>
        </div>
      </section>
    </LandingVideo>
  );
}
