'use client';

import { useEffect, useRef, useState } from 'react';
import { LandingVideo } from './LandingVideo';
import { BurnedCaption } from './BurnedCaption';

// The stage is drawn at a fixed 1312×640 and scaled to fit, so the player,
// timeline, phones and the connectors between them stay aligned at any width.
const STAGE_W = 1312;
const STAGE_H = 660;

/** Waveform bar heights plus whether each bar falls inside a found moment. */
function waveform(count: number, maxHeight: number, moments: Array<[number, number]>) {
  return Array.from({ length: count }, (_, i) => {
    const t = i / count;
    const h = maxHeight * (0.2 + Math.abs(Math.sin(i * 0.61) * 0.48 + Math.sin(i * 0.17) * 0.3));
    return { h: Math.round(Math.min(h, maxHeight)), hot: moments.some(([a, b]) => t >= a && t < b) };
  });
}

// Moments as fractions of the 58:12 source; the highlight boxes sit on these bars.
const MOMENTS: Array<[number, number]> = [
  [0.146, 0.24],
  [0.477, 0.593],
  [0.754, 0.838],
];
const BARS = waveform(130, 54, MOMENTS);
const MOBILE_BARS = waveform(60, 28, MOMENTS);

// Clips 01–03 land on the phones right to left, so the connectors nest instead of crossing.
const CLIPS = [
  { label: 'CLIP 03', score: '81 · TAKEAWAY', lines: ['Nobody tells', 'you this'], highlight: 'tells', length: '0:33', position: '22% 50%' },
  { label: 'CLIP 02', score: '88 · STORY', lines: ['The channel', 'started growing'], highlight: 'started', length: '0:58', position: '72% 50%' },
  { label: 'CLIP 01', score: '94 · HOOK', lines: ['Stop chasing', 'views'], highlight: 'chasing', length: '0:41', position: '48% 50%' },
];

// Horizontal centres of the three 144px phones, where the connectors land.
const PHONE_CENTRES = [940, 1090, 1240];

const TIMECODES = ['00:00', '14:30', '29:05', '43:40', '58:12'];

function useStageScale() {
  const ref = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setScale(Math.min(1, entry.contentRect.width / STAGE_W)));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return { ref, scale };
}

function ClipPhone({ clip, className }: { clip: (typeof CLIPS)[number]; className: string }) {
  return (
    <LandingVideo
      clip="podcast"
      position={clip.position}
      className={`rounded-[22px] border border-neutral-700 shadow-[0_30px_60px_rgba(0,0,0,0.55)] ${className}`}
    >
      <span className="absolute left-3 top-3 rounded-full bg-amber-500 px-2 py-1 font-jetbrains text-[10px] font-bold text-neutral-950">
        {clip.score}
      </span>
      <BurnedCaption lines={clip.lines} highlight={clip.highlight} className="absolute inset-x-1 bottom-[50px] text-[13px]" />
      <span className="absolute bottom-3 right-3 font-jetbrains text-[10px] text-neutral-200">{clip.length}</span>
    </LandingVideo>
  );
}

function SourcePlayer({ className }: { className: string }) {
  return (
    <LandingVideo clip="podcast" className={`rounded-[18px] border border-neutral-800 ${className}`}>
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(10,10,10,0.55)_0%,rgba(10,10,10,0)_22%,rgba(10,10,10,0)_60%,rgba(10,10,10,0.85)_100%)]" />
      <div className="absolute left-[2.2%] top-[3.5%] flex gap-2 font-jetbrains text-[11px] tracking-[0.08em] text-neutral-200">
        <span className="rounded-lg bg-neutral-950/70 px-2.5 py-1.5">SOURCE · 16:9</span>
        <span className="hidden rounded-lg bg-neutral-950/70 px-2.5 py-1.5 sm:inline">PODCAST · 58:12</span>
      </div>
      {/* 9:16 crop window tracking the speaker: 259 of 820 px wide, starting at 404. */}
      <div className="absolute inset-y-0 left-[49.27%] w-[31.59%] rounded-md border-2 border-dashed border-amber-500 shadow-[0_0_0_9999px_rgba(10,10,10,0.38)]">
        <span className="absolute left-2.5 top-3.5 whitespace-nowrap rounded-md bg-amber-500 px-2 py-1 font-jetbrains text-[10px] font-bold tracking-[0.06em] text-neutral-950">
          9:16<span className="hidden sm:inline"> · TRACKING SPEAKER</span>
        </span>
      </div>
      <p className="absolute inset-x-[2.7%] bottom-[4%] hidden text-[15px] leading-normal text-neutral-300 sm:block">
        …and honestly,{' '}
        <mark className="rounded bg-amber-500/30 px-1 text-white">
          the day I stopped chasing views was the day the channel started growing.
        </mark>{' '}
        Nobody tells you that part…
      </p>
    </LandingVideo>
  );
}

export function HeroStage() {
  const { ref, scale } = useStageScale();

  return (
    <>
      <div ref={ref} className="hidden lg:block" style={{ height: STAGE_H * scale }}>
        <div className="relative origin-top-left" style={{ width: STAGE_W, height: STAGE_H, transform: `scale(${scale})` }}>
          <SourcePlayer className="absolute left-0 top-0 h-[461px] w-[820px]" />

          <div className="absolute left-0 top-[484px] h-[112px] w-[820px] rounded-[14px] border border-neutral-800 bg-[#121212] px-4 py-3">
            <div className="flex justify-between font-jetbrains text-[10px] text-neutral-500">
              {TIMECODES.map((t) => (
                <span key={t}>{t}</span>
              ))}
            </div>
            <div className="relative mt-2.5 h-14" aria-hidden="true">
              <div className="absolute inset-0 flex items-center gap-0.5">
                {BARS.map((bar, i) => (
                  <span key={i} className={`flex-1 rounded-sm ${bar.hot ? 'bg-amber-500' : 'bg-neutral-700'}`} style={{ height: bar.h }} />
                ))}
              </div>
              {MOMENTS.map(([a, b], i) => (
                <div
                  key={a}
                  className="absolute -top-1 h-16 rounded-lg border-2 border-amber-500 bg-amber-500/15"
                  style={{ left: `calc(${a * 100}% - 3px)`, width: `calc(${(b - a) * 100}% + 4px)` }}
                >
                  <span className="absolute left-0 top-[66px] whitespace-nowrap font-jetbrains text-[10px] font-bold text-amber-400">
                    CLIP 0{i + 1} · {CLIPS[2 - i].score.split(' ')[0]}
                  </span>
                </div>
              ))}
              <div className="landing-playhead absolute -top-2 h-[72px] w-0.5 bg-white" />
            </div>
          </div>

          <svg width={STAGE_W} height={STAGE_H} viewBox={`0 0 ${STAGE_W} ${STAGE_H}`} fill="none" aria-hidden="true" className="pointer-events-none absolute inset-0">
            {[
              'M167 604 C167 648, 1240 648, 1240 348',
              'M437 604 C437 636, 1090 636, 1090 348',
              'M643 604 C643 624, 940 624, 940 348',
            ].map((d) => (
              <path key={d} d={d} stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="4 5" opacity="0.85" />
            ))}
            {PHONE_CENTRES.map((cx) => (
              <circle key={cx} cx={cx} cy="348" r="3.5" fill="#f59e0b" />
            ))}
          </svg>

          <ClipPhone clip={CLIPS[0]} className="absolute left-[868px] top-[34px] h-64 w-36 -rotate-[5deg]" />
          <ClipPhone clip={CLIPS[1]} className="absolute left-[1018px] top-0 z-10 h-64 w-36 border-neutral-600" />
          <ClipPhone clip={CLIPS[2]} className="absolute left-[1168px] top-[34px] h-64 w-36 rotate-[5deg]" />

          {PHONE_CENTRES.map((x, i) => (
            <span key={x} className="absolute top-[318px] -translate-x-1/2 font-jetbrains text-[10px] font-bold text-neutral-400" style={{ left: x }}>
              {CLIPS[i].label}
            </span>
          ))}
        </div>
      </div>

      <div className="space-y-4 lg:hidden">
        <SourcePlayer className="relative aspect-video w-full" />
        <div className="flex h-8 items-center gap-0.5" aria-hidden="true">
          {MOBILE_BARS.map((bar, i) => (
            <span key={i} className={`flex-1 rounded-sm ${bar.hot ? 'bg-amber-500' : 'bg-neutral-700'}`} style={{ height: bar.h }} />
          ))}
        </div>
        <div className="grid grid-cols-3 gap-3 pt-2">
          {[...CLIPS].reverse().map((clip) => (
            <LandingVideo key={clip.label} clip="podcast" position={clip.position} className="relative aspect-[9/16] rounded-2xl border border-neutral-700">
              <span className="absolute left-2 top-2 rounded-full bg-amber-500 px-1.5 py-0.5 font-jetbrains text-[9px] font-bold text-neutral-950">
                {clip.score.split(' ')[0]}
              </span>
              <BurnedCaption lines={clip.lines} highlight={clip.highlight} className="absolute inset-x-1 bottom-6 text-[10px] sm:text-sm" />
            </LandingVideo>
          ))}
        </div>
      </div>
    </>
  );
}
