import { SectionIntro } from './SectionIntro';

const STEPS = [
  {
    title: 'Add your video',
    body: 'Paste a YouTube link or upload a file. Clipnera transcribes every word with timestamps, so cuts land between words.',
  },
  {
    title: 'Review what it found',
    body: 'Each clip shows its score and why it was picked: hook, story, emotion or takeaway. Trim it, restyle the captions, or skip it.',
  },
  {
    title: 'Post or download',
    body: 'Edit the suggested title and hashtags, then publish to your channels or download the MP4 for anywhere else.',
  },
];

export function StepsSection({ onLaunchStudio }: { onLaunchStudio: () => void }) {
  return (
    <section id="how-it-works" className="scroll-mt-20 border-t border-neutral-900 py-20 lg:py-28">
      <div className="mx-auto max-w-[1240px] px-4 sm:px-8">
        <SectionIntro eyebrow="00:24 · How it works" title="Link to post in three steps." />

        <ol className="relative mt-16 grid gap-10 md:grid-cols-3 md:gap-8">
          <span
            aria-hidden="true"
            className="absolute inset-x-0 top-[23px] hidden h-0.5 bg-[repeating-linear-gradient(90deg,#404040_0_8px,transparent_8px_14px)] md:block"
          />
          {STEPS.map((step, i) => (
            <li key={step.title} className="relative space-y-3">
              <span className="grid h-12 w-12 place-items-center rounded-[14px] bg-amber-500 font-jetbrains text-[15px] font-bold text-neutral-950">
                0{i + 1}
              </span>
              <h3 className="font-syne text-2xl font-bold tracking-[-0.02em] text-white">{step.title}</h3>
              <p className="text-base leading-relaxed text-neutral-400">{step.body}</p>
            </li>
          ))}
        </ol>

        <div className="mt-14 flex flex-wrap items-center gap-4">
          <button
            type="button"
            onClick={onLaunchStudio}
            className="flex h-12 items-center rounded-xl bg-amber-500 px-6 text-base font-extrabold text-neutral-950 transition-colors hover:bg-amber-400 active:scale-[0.98]"
          >
            Try it on your video
          </button>
          <span className="text-[15px] text-neutral-400">Free plan, no card needed</span>
        </div>
      </div>
    </section>
  );
}
