import { Pause } from 'lucide-react';
import { LANDING_CLIPS } from '@/lib/landingMedia';
import { LandingVideo } from './LandingVideo';
import { BurnedCaption } from './BurnedCaption';
import { SectionIntro } from './SectionIntro';

const CLIPS = [
  { title: 'The day I stopped chasing views', range: '04:12–04:53', length: '0:41', score: 94, why: 'Strong hook', position: '48% 50%' },
  { title: 'Why the channel started growing', range: '21:47–22:45', length: '0:58', score: 88, why: 'Story arc', position: '72% 50%' },
  { title: 'Nobody tells you this part', range: '38:05–38:38', length: '0:33', score: 81, why: 'Clear takeaway', position: '22% 50%' },
  { title: 'What I would do differently', range: '51:30–52:14', length: '0:44', score: 67, why: 'Quotable line', position: '60% 50%' },
];

const HASHTAGS = ['#creatortips', '#podcastclips', '#youtubegrowth'];

const panel = 'rounded-xl border border-neutral-800 bg-neutral-950 p-3.5';

function Toggle({ label, on }: { label: string; on: boolean }) {
  return (
    <div className={`${panel} flex items-center justify-between`}>
      <span className="text-sm font-semibold text-white">{label}</span>
      <span className="sr-only">{on ? 'On' : 'Off'}</span>
      <span aria-hidden="true" className={`flex h-5 w-9 rounded-full p-0.5 ${on ? 'justify-end bg-amber-500' : 'bg-neutral-700'}`}>
        <span className={`h-4 w-4 rounded-full ${on ? 'bg-neutral-950' : 'bg-neutral-400'}`} />
      </span>
    </div>
  );
}

/** A static picture of the results screen, so visitors know what they get before signing up. */
export function ResultsPreview() {
  return (
    <section id="results" className="scroll-mt-20 py-20 lg:py-24">
      <div className="mx-auto max-w-[1440px] space-y-12 px-4 sm:px-8 xl:px-16">
        <SectionIntro eyebrow="06 · What you get back" title={<>Ranked, captioned,<br />ready to review.</>} inline>
          This is the screen you land on. Every clip is already cut and styled. Check the title, tweak a word, then download or
          publish.
        </SectionIntro>

        <figure
          aria-label="Example of the Clipnera results screen"
          className="overflow-hidden rounded-[20px] border border-neutral-800 bg-[#111] shadow-[0_40px_100px_rgba(0,0,0,0.6)]"
        >
          <div className="flex h-14 items-center justify-between gap-4 border-b border-neutral-800 bg-[#141414] px-5">
            <div className="flex min-w-0 items-center gap-3.5">
              <span aria-hidden="true" className="hidden gap-1.5 sm:flex">
                {[0, 1, 2].map((i) => (
                  <span key={i} className="h-2.5 w-2.5 rounded-full bg-neutral-700" />
                ))}
              </span>
              <span className="truncate text-sm font-bold text-white">Sample project · Studio podcast, full episode</span>
              <span className="hidden rounded-md bg-neutral-800 px-2 py-0.5 font-jetbrains text-[10px] text-neutral-400 sm:inline">58:12 SOURCE</span>
            </div>
            <span className="flex flex-shrink-0 items-center gap-2 text-[13px] text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              Clips ready
            </span>
          </div>

          <div className="grid lg:grid-cols-[420px_380px_minmax(0,1fr)]">
            <ul className="space-y-2 border-b border-neutral-800 p-4 lg:border-b-0 lg:border-r">
              <li className="flex justify-between px-1 pb-1 text-xs text-neutral-400">
                <span>Sorted by score</span>
                <span className="font-jetbrains">HIGH → LOW</span>
              </li>
              {CLIPS.map((clip, i) => (
                <li
                  key={clip.title}
                  className={`flex h-[132px] gap-3.5 rounded-[14px] border p-2.5 ${i === 0 ? 'border-amber-500 bg-[#1a1408]' : 'border-neutral-800 bg-[#141414]'}`}
                >
                  <img
                    src={LANDING_CLIPS.podcast.poster}
                    alt=""
                    loading="lazy"
                    className="h-28 w-[63px] flex-shrink-0 rounded-lg object-cover"
                    style={{ objectPosition: clip.position }}
                  />
                  <div className="flex min-w-0 flex-1 flex-col justify-between py-0.5">
                    <div className="space-y-1">
                      <p className="text-sm font-bold leading-snug text-white">{clip.title}</p>
                      <p className="font-jetbrains text-[10px] text-neutral-500">
                        {clip.range} · {clip.length}
                      </p>
                    </div>
                    <p className="flex items-center gap-2">
                      <span
                        className={`rounded-full px-2 py-0.5 font-jetbrains text-[11px] font-bold ${clip.score >= 80 ? 'bg-amber-500 text-neutral-950' : 'bg-neutral-800 text-neutral-200'}`}
                      >
                        {clip.score}
                      </span>
                      <span className="text-xs text-neutral-400">{clip.why}</span>
                    </p>
                  </div>
                </li>
              ))}
            </ul>

            <div className="flex items-center justify-center border-b border-neutral-800 bg-[#0d0d0d] py-8 lg:border-b-0 lg:border-r lg:py-0">
              <LandingVideo clip="podcast" position="48% 50%" className="relative h-[533px] w-[300px] rounded-[22px] border border-neutral-700">
                <div className="absolute inset-x-0 bottom-0 h-[45%] bg-gradient-to-b from-transparent to-black/70" />
                <BurnedCaption lines={['Stop chasing', 'views']} highlight="chasing" className="absolute inset-x-3 bottom-[110px] text-[26px]" />
                <div className="absolute inset-x-3.5 bottom-4 flex items-center gap-2.5">
                  <span aria-hidden="true" className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-white/90 text-neutral-950">
                    <Pause className="h-3.5 w-3.5 fill-current" />
                  </span>
                  <span className="flex h-1 flex-1 rounded-full bg-white/30">
                    <span className="w-[38%] rounded-full bg-amber-500" />
                  </span>
                  <span className="font-jetbrains text-[10px] text-neutral-200">0:15 / 0:41</span>
                </div>
              </LandingVideo>
            </div>

            <div className="flex flex-col gap-5 p-6 lg:px-7">
              <div className="space-y-2">
                <p className="text-xs font-semibold text-neutral-400">Title · suggested</p>
                <p className="flex h-11 items-center rounded-[10px] border border-neutral-700 bg-neutral-950 px-3.5 text-sm text-white">
                  The day I stopped chasing views
                </p>
              </div>
              <div className="space-y-2">
                <p className="text-xs font-semibold text-neutral-400">Hashtags · suggested</p>
                <ul className="flex flex-wrap gap-2 text-[13px]">
                  {HASHTAGS.map((tag) => (
                    <li key={tag} className="rounded-full bg-neutral-800 px-2.5 py-1.5 text-white">
                      {tag}
                    </li>
                  ))}
                  <li className="rounded-full border border-dashed border-neutral-700 px-2.5 py-1.5 text-neutral-400">+ Add</li>
                </ul>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className={panel}>
                  <p className="text-xs text-neutral-400">Caption style</p>
                  <p className="text-sm font-bold text-white">Bold Pop</p>
                </div>
                <div className={panel}>
                  <p className="text-xs text-neutral-400">Framing</p>
                  <p className="text-sm font-bold text-white">Follow speaker</p>
                </div>
                <Toggle label="Noise reduction" on />
                <Toggle label="Auto-emoji" on={false} />
              </div>
              <div className={`${panel} space-y-2.5`}>
                <p className="text-xs text-neutral-400">Why this clip scored 94</p>
                <p className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-neutral-200">
                  <span>
                    <b className="text-amber-400">Hook</b> opens on a strong claim
                  </span>
                  <span>
                    <b className="text-amber-400">Takeaway</b> one clear lesson
                  </span>
                </p>
              </div>
              <div className="mt-auto grid grid-cols-2 gap-2.5">
                <span className="flex h-12 items-center justify-center rounded-xl border border-neutral-700 text-sm font-bold text-white">
                  Download MP4
                </span>
                <span className="flex h-12 items-center justify-center rounded-xl bg-amber-500 text-sm font-bold text-neutral-950">
                  Publish clip
                </span>
              </div>
            </div>
          </div>
        </figure>
      </div>
    </section>
  );
}
