'use client';

import { useEffect, useState } from 'react';
import { Pause, Play } from 'lucide-react';
import { LANDING_CLIPS, type LandingClipKey } from '@/lib/landingMedia';
import { getCaptionStyle, type CaptionPreset } from '@/lib/utils/captionStyles';
import { CaptionStylePreview } from '@/components/dashboard/CaptionStylePreview';
import { LandingVideo } from './LandingVideo';
import { SectionIntro } from './SectionIntro';

interface ResultClip {
  title: string;
  source: string;
  range: string;
  seconds: number;
  score: number;
  why: string;
  clip: LandingClipKey;
  position: string;
  caption: string[];
  preset: CaptionPreset;
  hashtags: string[];
  reasons: Array<[string, string]>;
}

const CLIPS: ResultClip[] = [
  {
    title: 'The day I stopped chasing views',
    source: 'Podcast · 58:12',
    range: '04:12–04:53',
    seconds: 41,
    score: 94,
    why: 'Strong hook',
    clip: 'podcast',
    position: '48% 50%',
    caption: ['Stop', 'chasing', 'views'],
    preset: 'lime_stack',
    hashtags: ['#creatortips', '#podcastclips', '#youtubegrowth'],
    reasons: [
      ['Hook', 'opens on a strong claim'],
      ['Takeaway', 'one clear lesson'],
    ],
  },
  {
    title: 'Why the channel started growing',
    source: 'Solo episode · 32:40',
    range: '21:47–22:45',
    seconds: 58,
    score: 88,
    why: 'Story arc',
    clip: 'host',
    position: '50% 50%',
    caption: ['It', 'finally', 'clicked'],
    preset: 'gold_stack',
    hashtags: ['#podcast', '#storytime', '#creatorlife'],
    reasons: [
      ['Story', 'setup, turn and payoff'],
      ['Emotion', 'honest, personal tone'],
    ],
  },
  {
    title: 'I almost quit that year',
    source: 'Interview · 46:30',
    range: '38:05–38:49',
    seconds: 44,
    score: 81,
    why: 'Emotional peak',
    clip: 'interview',
    position: '40% 40%',
    caption: ['I', 'almost', 'quit'],
    preset: 'simple',
    hashtags: ['#interview', '#motivation', '#behindthescenes'],
    reasons: [
      ['Emotion', 'a candid turning point'],
      ['Hook', 'first line sets the stakes'],
    ],
  },
  {
    title: 'Here is the real reason',
    source: 'Explainer · 14:05',
    range: '09:30–10:03',
    seconds: 33,
    score: 67,
    why: 'Quotable line',
    clip: 'talk',
    position: '50% 50%',
    caption: ['The', 'real', 'reason'],
    preset: 'spotlight',
    hashtags: ['#explained', '#learnontiktok', '#tips'],
    reasons: [
      ['Quote', 'a line people repeat'],
      ['Pacing', 'slower start, trim suggested'],
    ],
  },
];

const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

const panel = 'rounded-xl border border-neutral-800 bg-neutral-950 p-3.5';

function Toggle({ label, on, onToggle }: { label: string; on: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={onToggle}
      className={`${panel} flex items-center justify-between text-left transition-colors hover:border-neutral-600`}
    >
      <span className="text-sm font-semibold text-white">{label}</span>
      <span aria-hidden="true" className={`flex h-5 w-9 rounded-full p-0.5 transition-colors ${on ? 'justify-end bg-amber-500' : 'bg-neutral-700'}`}>
        <span className={`h-4 w-4 rounded-full ${on ? 'bg-neutral-950' : 'bg-neutral-400'}`} />
      </span>
    </button>
  );
}

interface ResultsPreviewProps {
  onLaunchStudio: () => void;
}

/** A working copy of the results screen: pick a clip, play it, and see its suggestions. */
export function ResultsPreview({ onLaunchStudio }: ResultsPreviewProps) {
  const [selected, setSelected] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const [titles, setTitles] = useState(() => CLIPS.map((c) => c.title));
  const [noiseReduction, setNoiseReduction] = useState(true);
  const [autoEmoji, setAutoEmoji] = useState(false);

  const clip = CLIPS[selected];
  const style = getCaptionStyle(clip.preset);

  // The progress bar runs on the clip's real length, whether or not its video file has loaded.
  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => setElapsed((t) => (t + 0.1) % clip.seconds), 100);
    return () => clearInterval(timer);
  }, [playing, clip.seconds]);

  const choose = (index: number) => {
    setSelected(index);
    setElapsed(0);
    setPlaying(true);
  };

  return (
    <section id="results" className="scroll-mt-20 py-20 lg:py-24">
      <div className="mx-auto max-w-[1440px] space-y-12 px-4 sm:px-8 xl:px-16">
        <SectionIntro eyebrow="06 · What you get back" title={<>Ranked, captioned,<br />ready to review.</>} inline>
          This is the screen you land on. Pick a clip to play it: each one is already cut, reframed and captioned, with a
          title and hashtags to edit before you publish.
        </SectionIntro>

        <div className="overflow-hidden rounded-[20px] border border-neutral-800 bg-[#111] shadow-[0_40px_100px_rgba(0,0,0,0.6)]">
          <div className="flex h-14 items-center justify-between gap-4 border-b border-neutral-800 bg-[#141414] px-5">
            <div className="flex min-w-0 items-center gap-3.5">
              <span aria-hidden="true" className="hidden gap-1.5 sm:flex">
                {[0, 1, 2].map((i) => (
                  <span key={i} className="h-2.5 w-2.5 rounded-full bg-neutral-700" />
                ))}
              </span>
              <span className="truncate text-sm font-bold text-white">Sample workspace · Latest uploads</span>
              <span className="hidden rounded-md bg-neutral-800 px-2 py-0.5 font-jetbrains text-[10px] text-neutral-400 sm:inline">
                {CLIPS.length} CLIPS
              </span>
            </div>
            <span className="flex flex-shrink-0 items-center gap-2 text-[13px] text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              Clips ready
            </span>
          </div>

          <div className="grid lg:grid-cols-[420px_380px_minmax(0,1fr)]">
            <div className="space-y-2 border-b border-neutral-800 p-4 lg:border-b-0 lg:border-r">
              <p className="flex justify-between px-1 pb-1 text-xs text-neutral-400">
                <span>Sorted by score</span>
                <span className="font-jetbrains">HIGH → LOW</span>
              </p>
              <ul role="list" aria-label="Clips" className="space-y-2">
                {CLIPS.map((c, i) => {
                  const active = i === selected;
                  return (
                    <li key={c.title}>
                      <button
                        type="button"
                        onClick={() => choose(i)}
                        aria-pressed={active}
                        className={`flex h-[132px] w-full gap-3.5 rounded-[14px] border p-2.5 text-left transition-colors ${
                          active ? 'border-amber-500 bg-[#1a1408]' : 'border-neutral-800 bg-[#141414] hover:border-neutral-600'
                        }`}
                      >
                        <span className="relative h-28 w-[63px] flex-shrink-0 overflow-hidden rounded-lg bg-neutral-900">
                          <img
                            src={LANDING_CLIPS[c.clip].poster}
                            alt=""
                            loading="lazy"
                            className="h-full w-full object-cover text-transparent"
                            style={{ objectPosition: c.position }}
                          />
                          {active && playing && (
                            <span className="absolute bottom-1 left-1 flex h-4 items-end gap-px rounded bg-neutral-950/80 px-1 pb-0.5" aria-hidden="true">
                              {[0, 1, 2].map((b) => (
                                <span key={b} className="w-0.5 animate-pulse bg-amber-400" style={{ height: `${6 + b * 2}px`, animationDelay: `${b * 150}ms` }} />
                              ))}
                            </span>
                          )}
                        </span>
                        <span className="flex min-w-0 flex-1 flex-col justify-between py-0.5">
                          <span className="space-y-1">
                            <span className="block text-sm font-bold leading-snug text-white">{titles[i]}</span>
                            <span className="block font-jetbrains text-[10px] text-neutral-500">
                              {c.source} · {c.range}
                            </span>
                          </span>
                          <span className="flex items-center gap-2">
                            <span
                              className={`rounded-full px-2 py-0.5 font-jetbrains text-[11px] font-bold ${
                                c.score >= 80 ? 'bg-amber-500 text-neutral-950' : 'bg-neutral-800 text-neutral-200'
                              }`}
                            >
                              {c.score}
                            </span>
                            <span className="text-xs text-neutral-400">
                              {c.why} · {clock(c.seconds)}
                            </span>
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>

            <div className="flex items-center justify-center border-b border-neutral-800 bg-[#0d0d0d] py-8 lg:border-b-0 lg:border-r lg:py-0">
              <LandingVideo
                key={clip.clip}
                clip={clip.clip}
                position={clip.position}
                paused={!playing}
                className="relative h-[533px] w-[300px] rounded-[22px] border border-neutral-700"
              >
                <div className="absolute inset-x-0 bottom-0 h-[45%] bg-gradient-to-b from-transparent to-black/70" />
                <span
                  className={`absolute left-3.5 top-3.5 rounded-lg px-2 py-1 font-jetbrains text-[10px] ${
                    noiseReduction ? 'bg-amber-500 font-bold text-neutral-950' : 'bg-neutral-950/80 text-neutral-400'
                  }`}
                >
                  {noiseReduction ? 'VOICE CLEANED' : 'RAW AUDIO'}
                </span>
                <span className="absolute right-3.5 top-3.5 rounded-full bg-neutral-950/80 px-2 py-1 font-jetbrains text-[10px] font-bold text-amber-400">
                  {clip.score}
                </span>
                <div className={`absolute inset-x-3 bottom-[110px] ${playing ? '' : '[&_.caption-preview-word]:[animation-play-state:paused]'}`}>
                  <CaptionStylePreview
                    key={`${clip.preset}-${autoEmoji}`}
                    config={style.config}
                    words={autoEmoji ? [...clip.caption, '🔥'] : clip.caption}
                    fontSize={28}
                    overlay
                  />
                </div>
                <div className="absolute inset-x-3.5 bottom-4 flex items-center gap-2.5">
                  <button
                    type="button"
                    onClick={() => setPlaying((p) => !p)}
                    aria-label={playing ? 'Pause clip' : 'Play clip'}
                    className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-white/90 text-neutral-950 transition-colors hover:bg-white"
                  >
                    {playing ? <Pause className="h-3.5 w-3.5 fill-current" aria-hidden="true" /> : <Play className="h-3.5 w-3.5 fill-current" aria-hidden="true" />}
                  </button>
                  <span className="flex h-1 flex-1 overflow-hidden rounded-full bg-white/30" aria-hidden="true">
                    <span className="rounded-full bg-amber-500" style={{ width: `${(elapsed / clip.seconds) * 100}%` }} />
                  </span>
                  <span className="font-jetbrains text-[10px] text-neutral-200">
                    {clock(elapsed)} / {clock(clip.seconds)}
                  </span>
                </div>
              </LandingVideo>
            </div>

            <div className="flex flex-col gap-5 p-6 lg:px-7">
              <div className="space-y-2">
                <label htmlFor="results-title" className="text-xs font-semibold text-neutral-400">
                  Title · suggested
                </label>
                <input
                  id="results-title"
                  type="text"
                  value={titles[selected]}
                  onChange={(e) => setTitles((all) => all.map((t, i) => (i === selected ? e.target.value : t)))}
                  className="h-11 w-full rounded-[10px] border border-neutral-700 bg-neutral-950 px-3.5 text-sm text-white focus:border-amber-500 focus:outline-none"
                />
              </div>
              <div className="space-y-2">
                <p className="text-xs font-semibold text-neutral-400">Hashtags · suggested</p>
                <ul className="flex flex-wrap gap-2 text-[13px]">
                  {clip.hashtags.map((tag) => (
                    <li key={tag} className="rounded-full bg-neutral-800 px-2.5 py-1.5 text-white">
                      {tag}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className={panel}>
                  <p className="text-xs text-neutral-400">Caption style</p>
                  <p className="text-sm font-bold text-white">{style.brandName}</p>
                </div>
                <div className={panel}>
                  <p className="text-xs text-neutral-400">Framing</p>
                  <p className="text-sm font-bold text-white">Follow speaker</p>
                </div>
                <Toggle label="Noise reduction" on={noiseReduction} onToggle={() => setNoiseReduction((v) => !v)} />
                <Toggle label="Auto-emoji" on={autoEmoji} onToggle={() => setAutoEmoji((v) => !v)} />
              </div>
              <div className={`${panel} space-y-2.5`}>
                <p className="text-xs text-neutral-400">Why this clip scored {clip.score}</p>
                <p className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-neutral-200">
                  {clip.reasons.map(([label, text]) => (
                    <span key={label}>
                      <b className="text-amber-400">{label}</b> {text}
                    </span>
                  ))}
                </p>
              </div>
              <div className="mt-auto grid grid-cols-2 gap-2.5">
                <button
                  type="button"
                  onClick={onLaunchStudio}
                  className="h-12 rounded-xl border border-neutral-700 text-sm font-bold text-white transition-colors hover:border-neutral-500"
                >
                  Download MP4
                </button>
                <button
                  type="button"
                  onClick={onLaunchStudio}
                  className="h-12 rounded-xl bg-amber-500 text-sm font-bold text-neutral-950 transition-colors hover:bg-amber-400"
                >
                  Publish clip
                </button>
              </div>
            </div>
          </div>
        </div>
        <p className="text-center text-xs text-neutral-500">Sample clips for illustration. Scores help you choose; they don't predict views.</p>
      </div>
    </section>
  );
}
