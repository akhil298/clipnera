'use client';

import { VideoLinkForm } from './VideoLinkForm';

interface BottomCtaProps {
  heroUrl: string;
  setHeroUrl: (url: string) => void;
  onLaunchStudio: () => void;
}

const SPROCKETS = 'absolute inset-x-0 h-3 bg-[repeating-linear-gradient(90deg,transparent_0_18px,#1a1a1a_18px_34px,transparent_34px_46px)]';

/** The end card: one more chance to paste a link, framed like a strip of film. */
export function BottomCta({ heroUrl, setHeroUrl, onLaunchStudio }: BottomCtaProps) {
  return (
    <section id="start" className="relative overflow-hidden bg-neutral-950 py-24 sm:py-32">
      <span aria-hidden="true" className={`${SPROCKETS} top-6`} />
      <span aria-hidden="true" className={`${SPROCKETS} bottom-6`} />
      <div className="mx-auto max-w-[1240px] px-4 sm:px-8">
        <p className="font-jetbrains text-xs font-bold uppercase tracking-[0.12em] text-amber-400">01:24 · End card</p>
        <h2 className="mt-5 max-w-[15ch] font-syne text-[44px] font-extrabold leading-[0.96] tracking-[-0.035em] text-white sm:text-7xl">
          Your next Shorts are <span className="text-amber-400">already recorded.</span>
        </h2>
        <div className="mt-10 max-w-[600px]">
          <VideoLinkForm id="cta-url" url={heroUrl} setUrl={setHeroUrl} onSubmit={onLaunchStudio} />
        </div>
        <p className="mt-4 text-[15px] text-neutral-400">Free plan, no card needed. Sign in with Google.</p>
      </div>
    </section>
  );
}
