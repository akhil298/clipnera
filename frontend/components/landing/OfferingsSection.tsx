import { ArrowDown } from 'lucide-react';
import { RESULTS } from '@/lib/landingResults';
import { SectionIntro } from './SectionIntro';

const chip = 'rounded-lg border px-2.5 py-1.5 font-jetbrains text-[11px] font-bold';

/** The three ways in: Shorts from a long video, reels from footage, and the editor that takes a brief. */
export function OfferingsSection() {
  const cards = [
    {
      badge: 'ALL PLANS',
      title: 'Shorts from long videos',
      body: 'Paste a link to a podcast, interview, stream or explainer. Get vertical clips that open on the hook, scored so you know which to post first.',
      visual: (
        <div className="flex items-center gap-3">
          {RESULTS.map((reel, i) => (
            <img
              key={reel.id}
              src={reel.poster}
              alt=""
              loading="lazy"
              className={`aspect-[9/16] w-[84px] rounded-xl border border-neutral-700 object-cover ${i === 1 ? '-translate-y-3.5' : ''}`}
            />
          ))}
        </div>
      ),
    },
    {
      badge: 'ALL PLANS · FULL EDIT ON PRO',
      title: 'Reels from your footage',
      body: 'Drop in videos, photos and a voiceover, or a YouTube link. You get one reel for each strong moment, cut to the voice and never mid-word.',
      visual: (
        <div className="flex flex-col items-center gap-3">
          <div className="flex gap-2">
            {['VIDEOS', 'PHOTOS', 'VOICEOVER'].map((c) => (
              <span key={c} className={`${chip} border-neutral-700 bg-neutral-900 text-neutral-200`}>{c}</span>
            ))}
          </div>
          <ArrowDown className="h-5 w-5 text-neutral-400" aria-hidden="true" />
          <div className="flex gap-2">
            {['REEL 1', 'REEL 2', 'REEL 3'].map((c) => (
              <span key={c} className={`${chip} border-amber-500 bg-amber-500 text-neutral-950`}>{c}</span>
            ))}
          </div>
        </div>
      ),
    },
    {
      badge: 'NEW · EDITOR',
      title: 'Describe the edit',
      body: 'Say what you want in plain words, Hinglish too. The AI builds the cut on a real timeline. Change it by asking or by dragging, with one undo history.',
      href: '/editor',
      visual: (
        <div className="flex w-[78%] flex-col gap-2.5">
          <p className="self-end rounded-xl rounded-br-sm bg-neutral-800 px-3 py-2 text-[13px] leading-snug text-white">
            Make it 30 seconds, cut to the beat, Hinglish captions
          </p>
          {[[3, 2, 4, 2], [2, 3, 5], [11]].map((track, row) => (
            <div key={row} className="flex h-4 gap-[3px]">
              {track.map((flex, i) => (
                <span
                  key={i}
                  className={`rounded ${row === 0 ? 'bg-amber-500' : row === 1 && i === 1 ? 'bg-amber-700' : 'bg-neutral-700'}`}
                  style={{ flex }}
                />
              ))}
            </div>
          ))}
        </div>
      ),
    },
  ];

  return (
    <section id="make" className="scroll-mt-20 border-t border-neutral-900 py-20 lg:py-28">
      <div className="mx-auto max-w-[1240px] space-y-14 px-4 sm:px-8">
        <SectionIntro eyebrow="00:12 · What you can make" title={<>Three ways in.<br />One place to finish.</>} inline>
          Start from a long video, a folder of footage, or a sentence describing what you want.
        </SectionIntro>

        <div className="grid gap-6 lg:grid-cols-3">
          {cards.map((card) => (
            <article
              key={card.title}
              className="flex flex-col overflow-hidden rounded-[22px] border border-neutral-800 bg-[#121212] transition-[transform,border-color] duration-300 hover:-translate-y-1 hover:border-neutral-700"
            >
              <div aria-hidden="true" className="flex h-[220px] items-center justify-center border-b border-neutral-800 bg-[#0f0f0f]">
                {card.visual}
              </div>
              <div className="flex flex-1 flex-col gap-3 p-7">
                <span
                  className={`self-start rounded-full border px-2.5 py-1 font-jetbrains text-[11.5px] font-bold tracking-[0.06em] ${
                    card.href ? 'border-amber-500 bg-amber-500 text-neutral-950' : 'border-neutral-700 text-neutral-300'
                  }`}
                >
                  {card.badge}
                </span>
                <h3 className="font-syne text-2xl font-bold tracking-[-0.02em] text-white">{card.title}</h3>
                <p className="text-base leading-relaxed text-neutral-400">{card.body}</p>
                {card.href && (
                  <a href={card.href} className="mt-auto pt-2 text-sm font-bold text-amber-400 hover:text-amber-300">
                    See the editor →
                  </a>
                )}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
