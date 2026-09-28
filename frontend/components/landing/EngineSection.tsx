import type { ReactNode } from 'react';
import { LANDING_CLIPS } from '@/lib/landingMedia';
import { BurnedCaption } from './BurnedCaption';
import { SectionIntro } from './SectionIntro';

const TRANSCRIPT = 'the day I stopped chasing views was the day the channel started growing'.split(' ');

const MOMENTS = [
  { at: '04:12', score: 94, bar: 'bg-amber-500', text: 'text-amber-500' },
  { at: '21:47', score: 88, bar: 'bg-amber-400', text: 'text-amber-400' },
  { at: '38:05', score: 81, bar: 'bg-amber-300', text: 'text-amber-300' },
  { at: '51:30', score: 46, bar: 'bg-neutral-500', text: 'text-neutral-400' },
];

const NOISY = Array.from({ length: 72 }, (_, i) => Math.round(20 + Math.abs(Math.sin(i * 0.5) * 18 + Math.sin(i * 0.13) * 10) * 0.6 + (i % 3) * 4));
const CLEAN = Array.from({ length: 72 }, (_, i) =>
  Math.round(Math.max(3, Math.abs(Math.sin(i * 0.5) * 18 + Math.sin(i * 0.13) * 10) * (i % 11 < 7 ? 1.4 : 0.15))),
);

function timestamp(index: number) {
  const seconds = 252 + index * 0.31;
  return `${Math.floor(seconds / 60)}:${(seconds % 60).toFixed(1).padStart(4, '0')}`;
}

function Bars({ heights, color }: { heights: number[]; color: string }) {
  return (
    <div className="flex h-14 items-center gap-0.5" aria-hidden="true">
      {heights.map((h, i) => (
        <span key={i} className={`flex-1 rounded-sm ${color}`} style={{ height: Math.min(h, 56) }} />
      ))}
    </div>
  );
}

const Label = ({ children, accent = false }: { children: ReactNode; accent?: boolean }) => (
  <span className={`font-jetbrains text-[10px] uppercase ${accent ? 'text-amber-400' : 'text-neutral-500'}`}>{children}</span>
);

const STAGES: Array<{ step: string; title: string; body: string; visual: ReactNode }> = [
  {
    step: '01 · Listen',
    title: 'Every word, timestamped',
    body: "A word-level transcript is the map. It's what lets cuts land between words, never mid-sentence.",
    visual: (
      <div className="flex h-full flex-wrap content-center gap-x-1.5 gap-y-2 p-6">
        {TRANSCRIPT.map((word, i) => (
          <span
            key={i}
            className={`flex flex-col items-center gap-0.5 rounded-lg px-2 py-1.5 ${word === 'chasing' ? 'bg-amber-500 text-neutral-950' : 'bg-neutral-800 text-neutral-200'}`}
          >
            <span className="font-jetbrains text-[9px] opacity-75">{timestamp(i)}</span>
            <span className="text-[15px] font-semibold">{word}</span>
          </span>
        ))}
      </div>
    ),
  },
  {
    step: '02 · Score',
    title: 'Moments ranked 0–100',
    body: "AI reads for strong hooks and quotable lines. Scores help you choose what to post first; they don't predict views.",
    visual: (
      <div className="flex h-full flex-col justify-center gap-3 px-6">
        {MOMENTS.map((m) => (
          <div key={m.at} className="flex items-center gap-3">
            <span className="w-14 font-jetbrains text-[11px] text-neutral-500">{m.at}</span>
            <span className="h-2.5 flex-1 overflow-hidden rounded-full bg-neutral-800">
              <span className={`block h-full rounded-full ${m.bar}`} style={{ width: `${m.score}%` }} />
            </span>
            <span className={`w-8 text-right font-jetbrains text-[13px] font-bold ${m.text}`}>{m.score}</span>
          </div>
        ))}
        <span className="text-[11px] text-neutral-500">Hook · emotion · takeaway · shareability</span>
      </div>
    ),
  },
  {
    step: '03 · Reframe',
    title: 'The frame follows the face',
    body: 'Speakers are tracked and kept centred in the vertical crop, so nobody gets cut off mid-thought.',
    visual: (
      <div className="relative h-full">
        <img src={LANDING_CLIPS.host.poster} alt={LANDING_CLIPS.host.alt} loading="lazy" className="h-full w-full object-cover" />
        <div className="absolute inset-y-0 left-[36%] aspect-[9/16] border-2 border-amber-500 shadow-[0_0_0_9999px_rgba(10,10,10,0.55)]" />
        <span className="absolute bottom-3 left-3 rounded-md bg-neutral-950/80 px-2 py-1 font-jetbrains text-[10px] text-neutral-200">
          16:9 → 9:16 · FACE LOCK
        </span>
      </div>
    ),
  },
  {
    step: '04 · Clean audio',
    title: 'Hum out, voice in',
    body: "Steady noise like fans, AC and electrical hum is reduced and voice tone is evened out. Loud overlapping sound can't be fully removed.",
    visual: (
      <div className="flex h-full flex-col justify-center gap-3 px-6">
        <Label>Before · fan hum + room echo</Label>
        <Bars heights={NOISY} color="bg-neutral-600" />
        <Label accent>After · voice only</Label>
        <Bars heights={CLEAN} color="bg-amber-500" />
      </div>
    ),
  },
  {
    step: '05 · Caption',
    title: 'Word-by-word, burned in',
    body: 'Animated captions timed to each word, in a preset you pick, with optional auto-emoji. Editable before export.',
    visual: (
      <div className="flex h-full items-center justify-center">
        <div className="relative h-[220px] w-[124px] overflow-hidden rounded-2xl border border-neutral-700">
          <img src={LANDING_CLIPS.talk.poster} alt={LANDING_CLIPS.talk.alt} loading="lazy" className="h-full w-full object-cover" />
          <BurnedCaption lines={["Here's the", 'real reason']} highlight="real" className="absolute inset-x-1 bottom-11 text-[13px]" />
        </div>
      </div>
    ),
  },
  {
    step: '06 · B-roll',
    title: 'Cutaways where they fit',
    body: 'When the speaker mentions something visual, a matching cutaway is laid over the talking head to hold attention.',
    visual: (
      <div className="flex h-full flex-col justify-center gap-2.5 px-6">
        <Label>A-roll</Label>
        <div className="flex h-14 gap-0.5 overflow-hidden rounded-md opacity-90">
          {['30% 50%', '50% 50%', '70% 50%'].map((pos) => (
            <img key={pos} src={LANDING_CLIPS.podcast.poster} alt="" loading="lazy" className="h-full min-w-0 flex-1 object-cover" style={{ objectPosition: pos }} />
          ))}
        </div>
        <Label accent>B-roll cutaway · "while I was cooking…"</Label>
        <div className="relative h-14">
          <img
            src={LANDING_CLIPS.cook.poster}
            alt={LANDING_CLIPS.cook.alt}
            loading="lazy"
            className="absolute left-[36%] h-full w-[30%] rounded-md border-2 border-amber-500 object-cover"
          />
        </div>
      </div>
    ),
  },
];

/** The six pipeline stages, each with a small visual of what that stage does. */
export function EngineSection() {
  return (
    <section id="how-it-works" className="scroll-mt-20 py-20 lg:py-24">
      <div className="mx-auto max-w-[1440px] space-y-12 px-4 sm:px-8 xl:px-16">
        <SectionIntro eyebrow="03 · What happens after you paste the link" title={<>Six editing jobs.<br />Done before your coffee cools.</>}>
          No timeline scrubbing. Each card is the real step your video goes through, in order, with you in control at the end.
        </SectionIntro>

        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {STAGES.map((stage) => (
            <article key={stage.step} className="flex flex-col overflow-hidden rounded-[20px] border border-neutral-800 bg-[#121212]">
              <div className="h-[250px] overflow-hidden border-b border-neutral-800 bg-[#161616]">{stage.visual}</div>
              <div className="space-y-2 p-6">
                <p className="font-jetbrains text-xs uppercase text-amber-400">{stage.step}</p>
                <h3 className="font-syne text-2xl font-bold text-white">{stage.title}</h3>
                <p className="text-sm leading-relaxed text-neutral-400">{stage.body}</p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
