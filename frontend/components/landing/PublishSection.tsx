'use client';

import { useState, type ReactNode } from 'react';
import { BarChart2, Bookmark, Heart, MessageCircle, Music2, Repeat2, Send, Share2, ThumbsDown, ThumbsUp } from 'lucide-react';
import { LandingVideo } from './LandingVideo';
import { BurnedCaption } from './BurnedCaption';
import { SectionIntro } from './SectionIntro';

type PlatformId = 'shorts' | 'tiktok' | 'reels' | 'x';

// Names only, and generic icons: no third-party logos.
const PLATFORMS: Array<{ id: PlatformId; name: string; pro: boolean }> = [
  { id: 'shorts', name: 'YouTube Shorts', pro: false },
  { id: 'tiktok', name: 'TikTok', pro: false },
  { id: 'reels', name: 'Instagram Reels', pro: false },
  { id: 'x', name: 'X', pro: true },
];

const TITLE = 'The day I stopped chasing views';
const HASHTAGS = '#creatortips #podcastclips #youtubegrowth';

/** The finished clip as it plays on a phone; `rail` keeps the caption clear of a right-hand button rail. */
function Clip({ children, rail = true }: { children?: ReactNode; rail?: boolean }) {
  return (
    <LandingVideo clip="podcast" position="48% 50%" className="absolute inset-0">
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(0,0,0,0.35)_0%,rgba(0,0,0,0)_22%,rgba(0,0,0,0)_55%,rgba(0,0,0,0.8)_100%)]" />
      <BurnedCaption lines={['Stop chasing', 'views']} highlight="chasing" className={`absolute left-3 top-[30%] text-[19px] ${rail ? 'right-12' : 'right-3'}`} />
      {children}
    </LandingVideo>
  );
}

function ActionRail({ icons }: { icons: Array<{ Icon: typeof Heart; label: string }> }) {
  return (
    <div className="absolute bottom-16 right-2 flex flex-col items-center gap-3.5 text-white" aria-hidden="true">
      {icons.map(({ Icon, label }) => (
        <span key={label} className="flex flex-col items-center gap-0.5">
          <Icon className="h-[22px] w-[22px] drop-shadow" strokeWidth={2} />
          <span className="font-jetbrains text-[9px]">{label}</span>
        </span>
      ))}
    </div>
  );
}

function FeedMeta({ handle, children }: { handle: string; children?: ReactNode }) {
  return (
    <div className="absolute inset-x-3 bottom-3 space-y-1 pr-12 text-white">
      <p className="flex items-center gap-1.5 text-[12px] font-bold">
        <span aria-hidden="true" className="h-5 w-5 rounded-full bg-amber-500" />
        {handle}
      </p>
      <p className="line-clamp-2 text-[11px] leading-snug text-neutral-100">
        {TITLE} <span className="text-neutral-300">{HASHTAGS}</span>
      </p>
      {children}
    </div>
  );
}

const PREVIEWS: Record<PlatformId, ReactNode> = {
  shorts: (
    <Clip>
      <ActionRail
        icons={[
          { Icon: ThumbsUp, label: 'Like' },
          { Icon: ThumbsDown, label: 'Dislike' },
          { Icon: MessageCircle, label: 'Reply' },
          { Icon: Share2, label: 'Share' },
        ]}
      />
      <FeedMeta handle="@yourchannel">
        <span className="inline-block rounded bg-white/90 px-1.5 py-0.5 text-[10px] font-bold text-neutral-950">Subscribe</span>
      </FeedMeta>
    </Clip>
  ),
  tiktok: (
    <Clip>
      <ActionRail
        icons={[
          { Icon: Heart, label: 'Like' },
          { Icon: MessageCircle, label: 'Chat' },
          { Icon: Bookmark, label: 'Save' },
          { Icon: Share2, label: 'Share' },
        ]}
      />
      <FeedMeta handle="@yourchannel">
        <p className="flex items-center gap-1 text-[10px] text-neutral-200">
          <Music2 className="h-3 w-3" aria-hidden="true" /> original sound · yourchannel
        </p>
      </FeedMeta>
    </Clip>
  ),
  reels: (
    <Clip>
      <p className="absolute left-3 top-3 text-[15px] font-bold text-white drop-shadow">Reels</p>
      <ActionRail
        icons={[
          { Icon: Heart, label: 'Like' },
          { Icon: MessageCircle, label: 'Comment' },
          { Icon: Send, label: 'Send' },
        ]}
      />
      <FeedMeta handle="yourchannel">
        <p className="flex items-center gap-1 text-[10px] text-neutral-200">
          <Music2 className="h-3 w-3" aria-hidden="true" /> yourchannel · Original audio
        </p>
      </FeedMeta>
    </Clip>
  ),
  x: (
    <div className="absolute inset-0 flex flex-col bg-neutral-950 p-3 text-white">
      <p className="flex items-center gap-2 text-[12px]">
        <span aria-hidden="true" className="h-7 w-7 flex-shrink-0 rounded-full bg-amber-500" />
        <span>
          <b>Your Channel</b> <span className="text-neutral-500">@yourchannel · now</span>
        </span>
      </p>
      <p className="mt-2 text-[12px] leading-snug">
        {TITLE} <span className="text-sky-400">#creatortips</span>
      </p>
      <div className="relative mt-2.5 flex-1 overflow-hidden rounded-xl border border-neutral-800">
        <Clip rail={false} />
      </div>
      <p className="mt-2.5 flex justify-between px-1 text-neutral-500" aria-hidden="true">
        <MessageCircle className="h-4 w-4" />
        <Repeat2 className="h-4 w-4" />
        <Heart className="h-4 w-4" />
        <BarChart2 className="h-4 w-4" />
      </p>
    </div>
  ),
};

interface PublishSectionProps {
  onLaunchStudio: () => void;
}

/** One finished clip shown the way each platform will play it, with the publish bar that sends it there. */
export function PublishSection({ onLaunchStudio }: PublishSectionProps) {
  const [chosen, setChosen] = useState<Set<PlatformId>>(() => new Set<PlatformId>(['shorts', 'tiktok', 'reels']));
  const [scheduled, setScheduled] = useState(false);

  const toggle = (id: PlatformId) =>
    setChosen((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <section id="publish" className="scroll-mt-20 py-20 lg:py-24">
      <div className="mx-auto max-w-[1440px] space-y-12 px-4 sm:px-8 xl:px-16">
        <SectionIntro eyebrow="07 · Publish" title={<>One clip.<br />Every feed.</>} inline>
          The captions sit clear of every app's buttons. AI suggests a title and hashtags; edit them, then post to each
          platform at once, or download the MP4.
        </SectionIntro>

        <ul className="-mx-4 flex snap-x snap-mandatory scroll-px-4 gap-6 overflow-x-auto px-4 pb-2 [scrollbar-width:none] sm:mx-0 sm:px-0 lg:grid lg:grid-cols-4 lg:overflow-visible [&::-webkit-scrollbar]:hidden">
          {PLATFORMS.map((platform) => {
            const on = chosen.has(platform.id);
            return (
              <li key={platform.id} className="flex w-[260px] flex-shrink-0 snap-start flex-col items-center gap-4 lg:w-auto">
                <p className="flex w-full max-w-[260px] items-center justify-between text-sm font-bold text-white">
                  {platform.name}
                  <span
                    className={`rounded-full border px-2 py-0.5 font-jetbrains text-[10px] font-medium ${
                      platform.pro ? 'border-amber-500 text-amber-400' : 'border-neutral-700 text-neutral-400'
                    }`}
                  >
                    {platform.pro ? 'PRO' : 'DIRECT'}
                  </span>
                </p>
                <figure
                  aria-label={`The clip as it appears on ${platform.name}`}
                  className={`relative aspect-[9/16] w-full max-w-[260px] overflow-hidden rounded-[28px] border-[3px] bg-neutral-950 shadow-[0_30px_60px_rgba(0,0,0,0.5)] transition-[opacity,border-color,filter] duration-300 ${
                    on ? 'border-neutral-700' : 'border-neutral-900 opacity-40 grayscale'
                  }`}
                >
                  {PREVIEWS[platform.id]}
                </figure>
              </li>
            );
          })}
        </ul>

        <div className="flex flex-col gap-4 rounded-[20px] border border-neutral-800 bg-[#121212] p-4 lg:flex-row lg:items-center lg:justify-between lg:p-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="mr-1 text-xs font-semibold text-neutral-400">Post to</span>
            {PLATFORMS.map((platform) => {
              const on = chosen.has(platform.id);
              return (
                <button
                  key={platform.id}
                  type="button"
                  onClick={() => toggle(platform.id)}
                  aria-pressed={on}
                  className={`flex h-10 items-center gap-2 rounded-full border px-3.5 text-[13px] font-semibold transition-colors ${
                    on ? 'border-amber-500 bg-amber-500/10 text-white' : 'border-neutral-700 text-neutral-400 hover:text-white'
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className={`flex h-4 w-4 items-center justify-center rounded border text-[10px] ${
                      on ? 'border-amber-500 bg-amber-500 text-neutral-950' : 'border-neutral-600'
                    }`}
                  >
                    {on && '✓'}
                  </span>
                  {platform.name}
                  {platform.pro && <span className="font-jetbrains text-[10px] text-amber-400">PRO</span>}
                </button>
              );
            })}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div role="group" aria-label="When to post" className="flex rounded-full border border-neutral-700 p-1 text-[13px] font-semibold">
              {[
                { label: 'Post now', value: false },
                { label: 'Schedule · Pro', value: true },
              ].map((option) => (
                <button
                  key={option.label}
                  type="button"
                  onClick={() => setScheduled(option.value)}
                  aria-pressed={scheduled === option.value}
                  className={`h-8 rounded-full px-3.5 transition-colors ${
                    scheduled === option.value ? 'bg-neutral-700 text-white' : 'text-neutral-400 hover:text-white'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={onLaunchStudio}
              disabled={chosen.size === 0}
              className="h-11 rounded-xl bg-amber-500 px-5 text-sm font-bold text-neutral-950 transition-colors hover:bg-amber-400 disabled:cursor-not-allowed disabled:bg-neutral-800 disabled:text-neutral-500"
            >
              {chosen.size === 0 ? 'Pick a platform' : `${scheduled ? 'Schedule' : 'Publish'} to ${chosen.size} ${chosen.size === 1 ? 'platform' : 'platforms'}`}
            </button>
            <button
              type="button"
              onClick={onLaunchStudio}
              className="h-11 rounded-xl border border-neutral-700 px-4 text-sm font-bold text-white transition-colors hover:border-neutral-500"
            >
              Download MP4
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
