'use client';

import { Check } from 'lucide-react';
import { HERO_RESULT } from '@/lib/landingResults';
import { VideoLinkForm } from './VideoLinkForm';
import { LoopVideo } from './LoopVideo';

interface HeroSectionProps {
  heroUrl: string;
  setHeroUrl: (url: string) => void;
  onLaunchStudio: () => void;
  soundId: string | null;
  toggleSound: (id: string) => void;
}

const PROMISES = ['Free plan, no card', 'Free credits every 30 days', 'Captions in English, Hindi, Telugu, Hinglish and Tenglish'];

const FACTS = [
  ['FRAMED', 'Speaker kept in shot'],
  ['CAPTIONED', 'Word by word'],
  ['OPENS ON', 'The big question'],
];

const tag = 'pointer-events-none absolute left-2.5 top-2.5 rounded-md px-2 py-1 font-jetbrains text-[11px] font-bold tracking-[0.06em]';

/** The pitch beside one real before and after: the raw video Clipnera got and the reel it made. */
export function HeroSection({ heroUrl, setHeroUrl, onLaunchStudio, soundId, toggleSound }: HeroSectionProps) {
  const heroSoundId = `hero-${HERO_RESULT.id}`;

  return (
    <section className="pb-24 pt-12 lg:pt-16">
      <div className="mx-auto grid max-w-[1240px] items-center gap-14 px-4 sm:px-8 lg:grid-cols-[1.02fr_0.98fr] lg:gap-16">
        <header>
          <p className="font-jetbrains text-xs font-bold uppercase tracking-[0.12em] text-amber-400">
            For podcasters, YouTubers and anyone who talks on camera
          </p>
          <h1 className="mt-5 font-syne text-[46px] font-extrabold leading-[0.96] tracking-[-0.035em] text-white sm:text-7xl xl:text-[88px]">
            Record once.
            <br />
            <span className="text-amber-400">Post all week.</span>
          </h1>
          <p className="mt-7 max-w-[56ch] text-[17px] leading-relaxed text-neutral-300 sm:text-[19px]">
            Paste a YouTube link or upload a video. Clipnera finds the moments worth posting, keeps the speaker in frame,
            cleans up the audio and adds word-by-word captions. You pick the ones you like and post them.
          </p>
          <div className="mt-9 max-w-[560px]">
            <VideoLinkForm id="hero-url" url={heroUrl} setUrl={setHeroUrl} onSubmit={onLaunchStudio} />
            <p className="mt-3.5 text-[15px] text-neutral-400">
              Video on your computer?{' '}
              <button type="button" onClick={onLaunchStudio} className="font-semibold text-amber-400 underline-offset-2 hover:underline">
                Upload a file instead
              </button>
            </p>
          </div>
          <ul className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-[15px] text-neutral-400">
            {PROMISES.map((promise) => (
              <li key={promise} className="flex items-center gap-2">
                <Check className="h-4 w-4 text-emerald-400" aria-hidden="true" />
                {promise}
              </li>
            ))}
          </ul>
        </header>

        <figure className="grid grid-cols-[minmax(0,1fr)_minmax(0,0.62fr)] items-end gap-3 rounded-3xl border border-neutral-800 bg-[#0f0f0f] p-3 shadow-[0_30px_60px_-30px_rgba(0,0,0,0.8)] sm:gap-[18px] sm:p-[18px]">
          <div className="space-y-3.5">
            <LoopVideo
              src={HERO_RESULT.before.video}
              poster={HERO_RESULT.before.poster}
              label="Before: the raw landscape video"
              className="relative aspect-video rounded-xl"
              videoClassName="saturate-[0.75]"
            >
              <span className={`${tag} bg-neutral-950/80 text-neutral-200`}>BEFORE · RAW 16:9 · {HERO_RESULT.sourceLength}</span>
            </LoopVideo>
            <div aria-hidden="true" className="flex items-center gap-2.5 font-jetbrains text-xs text-neutral-400">
              <span>one click</span>
              <span className="h-0.5 flex-1 bg-[repeating-linear-gradient(90deg,#f59e0b_0_6px,transparent_6px_11px)]" />
              <span>{HERO_RESULT.reelLength} reel</span>
            </div>
            <ul className="grid gap-2 sm:grid-cols-3">
              {FACTS.map(([label, text]) => (
                <li key={label} className="rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2.5 text-[13px] leading-snug text-neutral-300">
                  <span className="block font-jetbrains text-[11px] font-bold tracking-[0.06em] text-amber-400">{label}</span>
                  {text}
                </li>
              ))}
            </ul>
          </div>
          <LoopVideo
            src={HERO_RESULT.video}
            poster={HERO_RESULT.poster}
            label={`After: the reel Clipnera made, “${HERO_RESULT.title}”`}
            className="relative aspect-[9/16] rounded-[20px]"
            sound={{ on: soundId === heroSoundId, onToggle: () => toggleSound(heroSoundId) }}
          >
            <span className={`${tag} bg-amber-500 text-neutral-950`}>AFTER</span>
          </LoopVideo>
          <figcaption className="col-span-2 px-0.5 text-[13px] text-neutral-400">
            Real Clipnera output, untouched. Made from a{' '}
            <a href={HERO_RESULT.sourceUrl} target="_blank" rel="noopener noreferrer" className="text-amber-400 underline-offset-2 hover:underline">
              {HERO_RESULT.creator} video
            </a>{' '}
            (CC BY). They aren&apos;t affiliated with Clipnera and don&apos;t endorse it.
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
