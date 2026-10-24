'use client';

import { RESULTS } from '@/lib/landingResults';
import { LoopVideo } from './LoopVideo';
import { SectionIntro } from './SectionIntro';

interface ResultsWallProps {
  soundId: string | null;
  toggleSound: (id: string) => void;
}

/** Reels straight out of Clipnera, each credited to the CC BY video it was cut from. */
export function ResultsWall({ soundId, toggleSound }: ResultsWallProps) {
  return (
    <section id="results" className="scroll-mt-20 border-t border-neutral-900 py-20 lg:py-28">
      <div className="mx-auto max-w-[1240px] space-y-12 px-4 sm:px-8">
        <SectionIntro eyebrow="00:03 · Real results" title={<>Made by Clipnera.<br />Not mocked up.</>} inline>
          Every reel here came straight out of Clipnera from someone&apos;s long video, with no hand edits afterwards. Tap one
          for sound.
        </SectionIntro>

        <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 sm:gap-6 lg:grid-cols-5">
          {RESULTS.map((reel) => (
            <li key={reel.id} className="flex flex-col gap-3">
              <LoopVideo
                src={reel.video}
                poster={reel.poster}
                label={`Reel: ${reel.title}`}
                className="relative aspect-[9/16] rounded-[22px] transition-transform duration-300 hover:-translate-y-1"
                sound={{ on: soundId === reel.id, onToggle: () => toggleSound(reel.id) }}
              />
              <p className="font-jetbrains text-xs font-bold text-amber-400">
                {reel.sourceLength} {reel.sourceKind} → {reel.reelLength} reel
              </p>
              <h3 className="text-base font-extrabold leading-snug text-white sm:text-lg">{reel.title}</h3>
              <p className="text-sm text-neutral-400">
                From{' '}
                <a href={reel.sourceUrl} target="_blank" rel="noopener noreferrer" className="text-amber-400 underline-offset-2 hover:underline">
                  {reel.creator}
                </a>{' '}
                (CC BY)
              </p>
            </li>
          ))}
        </ul>

        <p className="max-w-[80ch] text-[15px] text-neutral-400">
          Source videos are Creative Commons Attribution (CC BY) uploads by the people in them, credited and linked above.
          They aren&apos;t affiliated with Clipnera and don&apos;t endorse it. Your reels come from your own footage.
        </p>
      </div>
    </section>
  );
}
