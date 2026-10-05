import { AudioLines, Captions, Crop, Film, ListOrdered, ScrollText } from 'lucide-react';
import type { ReactNode } from 'react';

import { LANDING_CLIPS } from '@/lib/landingMedia';

import { BurnedCaption } from './BurnedCaption';
import { Section } from './Section';

const TRANSCRIPT = ['the', 'day', 'I', 'stopped', 'chasing', 'views', 'was', 'the', 'day', 'it', 'grew'];
const RANKED = [
  { at: '04:12', width: 'w-11/12', lead: true },
  { at: '21:47', width: 'w-5/6', lead: true },
  { at: '38:05', width: 'w-3/4', lead: true },
  { at: '51:30', width: 'w-2/5', lead: false },
];
/** Deterministic bar heights (percent) for the audio sketch; the same on server and client. */
const NOISY = Array.from({ length: 40 }, (_, i) => 45 + Math.round(Math.abs(Math.sin(i * 0.9)) * 35));
const CLEAN = Array.from({ length: 40 }, (_, i) => (i % 9 < 6 ? 25 + Math.round(Math.abs(Math.sin(i * 0.5)) * 70) : 6));

function Bars({ heights, tone }: { heights: number[]; tone: string }) {
  return (
    <span className="flex h-10 items-center gap-0.5">
      {heights.map((height, index) => (
        <span key={index} className={`flex-1 rounded-cn-xs ${tone}`} style={{ height: `${height}%` }} />
      ))}
    </span>
  );
}

const Tag = ({ children }: { children: ReactNode }) => <span className="text-cn-caption text-cn-fg-muted">{children}</span>;

const STEPS: Array<{ icon: ReactNode; step: string; title: string; body: string; visual: ReactNode }> = [
  {
    icon: <ScrollText />,
    step: 'Listen',
    title: 'Every word, timestamped',
    body: 'A word-level transcript is the map. It’s what lets cuts land between words, never mid-sentence.',
    visual: (
      <span className="flex flex-wrap content-center gap-1.5 p-5">
        {TRANSCRIPT.map((word, index) => (
          <span
            key={index}
            className={`rounded-cn-sm px-2 py-1 text-cn-label font-semibold ${word === 'chasing' ? 'bg-cn-accent-subtle text-cn-accent-text' : 'bg-cn-surface-active text-cn-fg-secondary'}`}
          >
            {word}
          </span>
        ))}
      </span>
    ),
  },
  {
    icon: <ListOrdered />,
    step: 'Rank',
    title: 'The strongest moments first',
    body: 'Hooks, stories and quotable lines are scored out of 100, so you start with the best. Scores help you choose; they don’t predict views.',
    visual: (
      <span className="flex h-full flex-col justify-center gap-3 px-5">
        {RANKED.map((moment) => (
          <span key={moment.at} className="flex items-center gap-3">
            <span className="w-12 font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">{moment.at}</span>
            <span className="h-2 flex-1 rounded-cn-full bg-cn-surface-active">
              <span className={`block h-full rounded-cn-full ${moment.width} ${moment.lead ? 'bg-cn-accent' : 'bg-cn-fg-muted'}`} />
            </span>
          </span>
        ))}
      </span>
    ),
  },
  {
    icon: <Crop />,
    step: 'Reframe',
    title: 'The frame follows the face',
    body: 'Speakers are tracked and kept centred in the 9:16 crop, so nobody is cut off mid-thought.',
    visual: (
      <span className="relative block h-full bg-cn-stage">
        <img src={LANDING_CLIPS.host.poster} alt="" loading="lazy" decoding="async" className="h-full w-full object-cover" />
        <span className="absolute inset-y-0 left-0 w-1/3 bg-cn-overlay/60" />
        <span className="absolute inset-y-0 right-0 w-1/3 bg-cn-overlay/60" />
        <span className="absolute inset-y-0 left-1/3 w-1/3 border-2 border-cn-accent" />
        <span className="absolute bottom-3 left-3 rounded-cn-xs bg-cn-stage/80 px-1.5 font-cn-mono text-cn-caption text-cn-fg" data-theme="dark">
          16:9 → 9:16
        </span>
      </span>
    ),
  },
  {
    icon: <AudioLines />,
    step: 'Clean audio',
    title: 'Hum out, voice in',
    body: 'Steady noise like fans, AC and electrical hum is reduced and voice tone evened out. Loud overlapping sound can’t be fully removed.',
    visual: (
      <span className="flex h-full flex-col justify-center gap-2 px-5">
        <Tag>Before · fan hum and room echo</Tag>
        <Bars heights={NOISY} tone="bg-cn-fg-muted" />
        <Tag>After · voice only</Tag>
        <Bars heights={CLEAN} tone="bg-cn-accent" />
      </span>
    ),
  },
  {
    icon: <Captions />,
    step: 'Caption',
    title: 'Word by word, burned in',
    body: 'Captions timed to each word in a style you pick, with optional auto-emoji. You can edit every line before export.',
    visual: (
      <span className="flex h-full items-center justify-center">
        <span className="relative block h-5/6 overflow-hidden rounded-cn-lg bg-cn-stage aspect-cn-portrait">
          <img src={LANDING_CLIPS.talk.poster} alt="" loading="lazy" decoding="async" className="h-full w-full object-cover" />
          <BurnedCaption lines={['Here’s the', 'real reason']} highlight="real" className="absolute inset-x-1 bottom-6 text-cn-label" />
        </span>
      </span>
    ),
  },
  {
    icon: <Film />,
    step: 'B-roll',
    title: 'Cutaways where they fit',
    body: 'When the speaker mentions something visual, a licensed cutaway is laid over the talking head to hold attention.',
    visual: (
      <span className="flex h-full flex-col justify-center gap-2 px-5">
        <Tag>Talking head</Tag>
        <span className="flex h-10 gap-0.5 overflow-hidden rounded-cn-sm">
          {['object-left', 'object-center', 'object-right'].map((crop) => (
            <img key={crop} src={LANDING_CLIPS.podcast.poster} alt="" loading="lazy" decoding="async" className={`h-full min-w-0 flex-1 object-cover ${crop}`} />
          ))}
        </span>
        <Tag>Cutaway · “while I was cooking…”</Tag>
        <span className="relative block h-10">
          <img
            src={LANDING_CLIPS.cook.poster}
            alt=""
            loading="lazy"
            decoding="async"
            className="absolute left-1/3 h-full w-1/3 rounded-cn-sm border-2 border-cn-accent object-cover"
          />
        </span>
      </span>
    ),
  },
];

/** The six steps every video goes through, each shown as a small picture of what it does. */
export function HowItWorks() {
  return (
    <Section
      id="how-it-works"
      title="Six editing jobs, done for you"
      intro="No timeline scrubbing. Each card is a real step your video goes through, in order, with you in control at the end."
    >
      <ol className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {STEPS.map((item, index) => (
          <li key={item.step} className="flex flex-col overflow-hidden rounded-cn-lg border border-cn-border bg-cn-surface">
            <div aria-hidden className="h-44 overflow-hidden border-b border-cn-border bg-cn-surface-sunken">
              {item.visual}
            </div>
            <div className="flex flex-col gap-2 p-5">
              <p className="inline-flex items-center gap-2 text-cn-label text-cn-fg-secondary [&_svg]:size-4">
                <span aria-hidden className="inline-flex text-cn-fg-muted">
                  {item.icon}
                </span>
                <span className="font-cn-mono tabular-nums text-cn-fg-muted">{index + 1}</span>
                {item.step}
              </p>
              <h3 className="text-cn-title-sm font-semibold text-cn-fg">{item.title}</h3>
              <p className="text-cn-body text-cn-fg-secondary">{item.body}</p>
            </div>
          </li>
        ))}
      </ol>
    </Section>
  );
}
