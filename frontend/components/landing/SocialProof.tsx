'use client';

const PLATFORMS = ['YouTube Shorts', 'TikTok', 'Instagram Reels', 'X'];

/** Where clips are made to go. Names only: no invented customers, counts or logos. */
export function SocialProof() {
  return (
    <section className="py-8 border-y border-neutral-800/80 bg-neutral-950/50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <p className="text-center text-xs font-semibold uppercase tracking-wider text-neutral-300 mb-6">
          Clips sized and captioned for
        </p>
        <ul className="flex flex-wrap items-center justify-center gap-8 sm:gap-14 text-neutral-300 font-extrabold text-sm sm:text-base">
          {PLATFORMS.map((platform) => (
            <li key={platform}>{platform}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
