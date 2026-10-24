import { SectionIntro } from './SectionIntro';

const JOBS = [
  { job: 'Finding moments', byHand: 'Watch the whole 46-minute interview', clipnera: 'Moments ranked 0–100, with why each was picked' },
  { job: 'Framing', byHand: 'Centre crop, speaker half out of shot', clipnera: 'The vertical crop follows the speaker' },
  { job: 'Audio', byHand: 'Fan hum and room echo', clipnera: 'Steady noise reduced, voice evened out' },
  { job: 'Captions', byHand: 'Typed and timed yourself', clipnera: 'Word-by-word, styled and burned in' },
  { job: 'Posting', byHand: 'Write every title from scratch', clipnera: 'Suggested title and hashtags you can edit' },
];

/** The editing jobs a long video needs before it can be posted, by hand and with Clipnera. */
export function ProblemSection() {
  return (
    <section id="problem" className="scroll-mt-20 border-t border-neutral-900 py-20 lg:py-28">
      <div className="mx-auto grid max-w-[1240px] gap-12 px-4 sm:px-8 lg:grid-cols-[0.9fr_1.1fr] lg:gap-[72px]">
        <SectionIntro eyebrow="00:09 · The problem" title="Recording was the easy part.">
          The hard part is scrubbing an hour of footage for forty good seconds, re-cropping so nobody&apos;s half out of frame,
          typing captions word by word and fighting the fan hum. Clipnera does that pass for you, so you only make the calls
          that need your taste.
        </SectionIntro>

        <table className="w-full border-collapse text-[15px] sm:text-base">
          <thead className="hidden sm:table-header-group">
            <tr className="text-left font-jetbrains text-xs tracking-[0.1em] text-neutral-400">
              <th scope="col" className="pb-3 font-medium">
                <span className="sr-only">Job</span>
              </th>
              <th scope="col" className="pb-3 font-medium">BY HAND</th>
              <th scope="col" className="pb-3 font-medium text-amber-400">WITH CLIPNERA</th>
            </tr>
          </thead>
          <tbody>
            {JOBS.map((row) => (
              <tr key={row.job} className="grid border-t border-neutral-800 py-3.5 sm:table-row sm:py-0">
                <th scope="row" className="text-left font-extrabold text-white sm:w-[24%] sm:py-[18px] sm:pr-3">
                  {row.job}
                </th>
                <td className="text-neutral-400 sm:py-[18px] sm:pr-3">
                  <span className="font-bold sm:hidden">Without: </span>
                  {row.byHand}
                </td>
                <td className="font-semibold text-white sm:py-[18px]">
                  <span className="font-extrabold text-amber-400 sm:hidden">Clipnera: </span>
                  {row.clipnera}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
