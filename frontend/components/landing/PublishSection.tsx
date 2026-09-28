import { LANDING_CLIPS, type LandingClipKey } from '@/lib/landingMedia';
import { SectionIntro } from './SectionIntro';

// Names only: no third-party logos.
const PLATFORMS: Array<{ name: string; note: string; clip: LandingClipKey; position: string; pro: boolean }> = [
  { name: 'YouTube Shorts', note: 'Vertical, captioned, with a suggested title.', clip: 'podcast', position: '72% 50%', pro: false },
  { name: 'TikTok', note: 'Caption and hashtags you can edit first.', clip: 'cook', position: '50% 50%', pro: false },
  { name: 'Instagram Reels', note: 'Same clip, sized and ready.', clip: 'talk', position: '50% 50%', pro: false },
  { name: 'X', note: 'Publish and schedule posts ahead.', clip: 'interview', position: '40% 50%', pro: true },
];

export function PublishSection() {
  return (
    <section id="publish" className="scroll-mt-20 py-20 lg:py-24">
      <div className="mx-auto max-w-[1440px] space-y-10 px-4 sm:px-8 xl:px-16">
        <SectionIntro eyebrow="07 · Publish" title={<>Straight to where<br />people scroll.</>} inline>
          AI suggests a title and hashtags for each clip. Edit them, then post, or download the MP4 for anywhere else.
        </SectionIntro>

        <ul className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
          {PLATFORMS.map((platform) => (
            <li key={platform.name} className="flex gap-4 rounded-[18px] border border-neutral-800 bg-[#121212] p-4">
              <img
                src={LANDING_CLIPS[platform.clip].poster}
                alt=""
                loading="lazy"
                className="h-[164px] w-[92px] flex-shrink-0 rounded-xl object-cover"
                style={{ objectPosition: platform.position }}
              />
              <div className="flex flex-col justify-between py-1">
                <div className="space-y-1.5">
                  <h3 className="font-syne text-xl font-bold leading-tight text-white">{platform.name}</h3>
                  <p className="text-[13px] leading-snug text-neutral-400">{platform.note}</p>
                </div>
                <span
                  className={`self-start rounded-full border px-2.5 py-1 font-jetbrains text-[10px] ${
                    platform.pro ? 'border-amber-500 text-amber-400' : 'border-neutral-700 text-neutral-300'
                  }`}
                >
                  {platform.pro ? 'PRO' : 'DIRECT PUBLISH'}
                </span>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
