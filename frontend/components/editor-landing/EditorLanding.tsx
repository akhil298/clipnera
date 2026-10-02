'use client';

import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowUp, Plus } from 'lucide-react';
import { isAuthenticated } from '@/lib/auth';
import { Navbar } from '@/components/landing/Navbar';
import { Footer } from '@/components/landing/Footer';
import { SignInModal } from '@/components/landing/SignInModal';

const PRESETS = ['Podcast to Shorts', 'Travel reel', 'Product launch', 'Talking head', 'Tutorial tips', 'Wedding teaser'];

/** CSS stand-ins for footage in the mock reels; no real media is needed for the page to read. */
const REELS = [
  { tag: 'Travel · 0:30', caption: 'Sunset run', bg: 'linear-gradient(180deg,#7dd3fc,#0e7490 55%,#fde68a 55% 62%,#b45309 62%)' },
  { tag: 'Podcast · 0:45', caption: 'The real reason', bg: 'radial-gradient(30% 18% at 50% 38%,#d9a07c 0 60%,transparent 61%),radial-gradient(70% 40% at 50% 100%,#1e3a5f 0 70%,transparent 71%),linear-gradient(#26324a,#0f1522)' },
  { tag: 'Product · 0:20', caption: 'Meet the new one', bg: 'radial-gradient(40% 25% at 50% 45%,#f5f5f4 0 50%,transparent 51%),linear-gradient(#fda4af,#9f1239)' },
  { tag: 'Hinglish · 0:38', caption: 'Yeh koi nahi batata', bg: 'radial-gradient(30% 18% at 50% 36%,#c08a66 0 60%,transparent 61%),radial-gradient(70% 40% at 50% 100%,#3f3f46 0 70%,transparent 71%),linear-gradient(#52525b,#18181b)' },
  { tag: 'Tutorial · 0:40', caption: 'Tip 2: shortcuts', bg: 'linear-gradient(135deg,#1e1b4b,#4338ca 50%,#0ea5e9)' },
];

const STEPS = [
  { n: '01', title: 'Drop and describe', body: 'Upload footage, paste a YouTube link, or reuse clips from earlier projects. Say what you want in your own words, Hinglish too.' },
  { n: '02', title: 'Direct the edit', body: 'The agent builds the first cut on a real timeline. Change anything by asking, or drag, trim and split yourself.' },
  { n: '03', title: 'Export or post', body: 'Render for Reels, Shorts or YouTube, post to your channels, or finish in Premiere and DaVinci.' },
];

const FEATURES = [
  { tag: 'Search', title: 'Find any moment by meaning', body: 'Search "the part where she laughs about pricing" and jump straight to it, across every file.' },
  { tag: 'First cut', title: 'Picks the moments that hold', body: "The engine behind Clipnera's clips chooses the hook, the order and the pacing." },
  { tag: 'Timeline', title: 'Chat or drag, one timeline', body: "Your edits and the agent's land on the same tracks, with one undo history." },
  { tag: 'Captions', title: '21 caption styles', body: 'Word-by-word captions in English, Hindi, Telugu, Hinglish and Tenglish, clear of app buttons.' },
  { tag: 'B-roll + music', title: 'Licensed, safe to post', body: 'B-roll and music from licensed libraries, with AI-generated shots on Pro.' },
  { tag: 'Your agent', title: 'Bring your own Claude', body: 'Connect Claude Code or the Claude app and edit your projects from there, on your own plan.' },
];

const FAQS = [
  { q: 'What can I upload?', a: 'Video, photos and audio, or a YouTube link. Pro projects take up to 60 minutes of footage across 100 files.' },
  { q: 'Can I edit by hand too?', a: 'Yes. Trim, split, move and delete on the timeline. The agent edits the same timeline, and every change can be undone.' },
  { q: 'Which languages work?', a: 'Prompts in English or Hinglish. Captions in English, Hindi, Telugu, Hinglish and Tenglish.' },
  { q: 'Is the music safe to post?', a: 'Yes. Music and B-roll come from libraries licensed for commercial use, and each export lists any credit a track needs.' },
];

/** ``className`` must position the card (``relative`` in a row, ``absolute`` when floating); its caption is placed inside it. */
function Reel({ caption, bg, tag, className }: { caption: string; bg: string; tag?: string; className: string }) {
  return (
    <div className={`aspect-[9/16] overflow-hidden rounded-2xl border border-white/10 ${className}`} style={{ background: bg }}>
      {tag && <span className="absolute left-2 top-2 rounded bg-black/55 px-1.5 py-0.5 font-jetbrains text-[10px] text-neutral-200">{tag}</span>}
      <span className="absolute inset-x-[7%] bottom-[18%] text-center font-syne text-sm font-extrabold uppercase leading-none text-white [text-shadow:0_2px_0_#000,0_0_6px_#000]">
        {caption}
      </span>
    </div>
  );
}

export default function EditorLanding() {
  const router = useRouter();
  const [signInOpen, setSignInOpen] = useState(false);
  const [brief, setBrief] = useState('');
  const closeSignIn = useCallback(() => setSignInOpen(false), []);

  /** Signed-in creators go straight to the editor, with what they typed as the new project's brief. */
  const start = (text = brief) => {
    if (!isAuthenticated()) {
      setSignInOpen(true);
      return;
    }
    const query = text.trim() ? `?brief=${encodeURIComponent(text.trim())}` : '';
    router.push(`/dashboard/editor${query}`);
  };

  return (
    <div className="min-h-screen bg-neutral-950 font-['Plus_Jakarta_Sans',sans-serif] text-neutral-100">
      <SignInModal open={signInOpen} onClose={closeSignIn} />
      <Navbar onOpenAuthModal={() => setSignInOpen(true)} onLaunchStudio={() => start('')} />

      <main id="main">
        <section className="relative overflow-hidden px-4 pb-24 pt-16 text-center sm:px-8">
          <Reel caption="Goa diaries" bg={REELS[0].bg} className="absolute left-[4%] top-[18%] hidden w-28 -rotate-[10deg] shadow-2xl lg:block" />
          <Reel caption="Nobody tells you" bg={REELS[1].bg} className="absolute left-[13%] top-[58%] hidden w-28 rotate-[7deg] shadow-2xl lg:block" />
          <Reel caption="Yeh sach hai" bg={REELS[3].bg} className="absolute right-[5%] top-[14%] hidden w-28 rotate-[9deg] shadow-2xl lg:block" />
          <Reel caption="Sunset run" bg={REELS[0].bg} className="absolute right-[12%] top-[56%] hidden w-28 -rotate-6 shadow-2xl lg:block" />

          <div className="relative z-10 mx-auto flex max-w-3xl flex-col items-center gap-6">
            <p className="font-jetbrains text-xs font-medium uppercase tracking-[0.14em] text-amber-400">New · Clipnera Editor</p>
            <h1 className="font-syne text-[44px] font-extrabold leading-[0.98] tracking-[-0.035em] text-white sm:text-6xl xl:text-[74px]">
              Describe it.
              <br />
              <span className="text-amber-500">We&apos;ll cut it.</span>
            </h1>
            <p className="max-w-[58ch] text-base leading-relaxed text-neutral-300 sm:text-[17px]">
              Drop in footage or a YouTube link and say what you want. The agent builds the edit on a real timeline: cuts,
              captions, B-roll and music. You direct the rest.
            </p>

            <form
              className="w-full max-w-[640px] rounded-[18px] border border-neutral-800 bg-neutral-900 p-3.5 text-left shadow-[0_30px_80px_-30px_rgba(245,158,11,0.25)]"
              onSubmit={(e) => {
                e.preventDefault();
                start();
              }}
            >
              <label htmlFor="editor-brief" className="sr-only">What should we make?</label>
              <textarea
                id="editor-brief"
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
                rows={2}
                maxLength={300}
                placeholder="Make a 30 s reel from my Goa trip, cut to the beat, Hinglish captions…"
                className="w-full resize-none bg-transparent px-1.5 py-1 text-base text-white placeholder:text-neutral-500 focus:outline-none"
              />
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => start()} aria-label="Add footage" className="grid h-8 w-8 place-items-center rounded-lg border border-neutral-800 bg-neutral-800 text-neutral-300 hover:text-white">
                  <Plus className="h-4 w-4" aria-hidden />
                </button>
                <button type="submit" aria-label="Start" className="ml-auto grid h-8 w-8 place-items-center rounded-lg bg-amber-500 text-neutral-950 hover:bg-amber-400">
                  <ArrowUp className="h-4 w-4" aria-hidden />
                </button>
              </div>
            </form>

            <div className="flex max-w-[680px] flex-wrap justify-center gap-2">
              {PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setBrief(`${preset}: `)}
                  className="rounded-full border border-neutral-800 bg-neutral-900 px-3.5 py-1.5 text-[13px] font-semibold text-neutral-300 hover:border-amber-500 hover:text-white"
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="border-t border-neutral-900 px-4 py-20 sm:px-8 xl:px-16">
          <div className="mx-auto max-w-[1200px]">
            <p className="font-jetbrains text-xs uppercase tracking-[0.14em] text-amber-400">Made with Clipnera</p>
            <h2 className="mt-2 font-syne text-3xl font-extrabold tracking-[-0.03em] sm:text-[44px]">Finished, captioned, ready to post.</h2>
            <div className="mt-8 grid auto-cols-[160px] grid-flow-col gap-3.5 overflow-x-auto pb-2">
              {REELS.map((reel) => <Reel key={reel.tag} {...reel} className="relative" />)}
            </div>
          </div>
        </section>

        <section className="border-t border-neutral-900 px-4 py-20 sm:px-8 xl:px-16">
          <div className="mx-auto max-w-[1200px]">
            <p className="font-jetbrains text-xs uppercase tracking-[0.14em] text-amber-400">How it works</p>
            <h2 className="mt-2 font-syne text-3xl font-extrabold tracking-[-0.03em] sm:text-[44px]">
              Your first edit in <span className="text-amber-500">three moves</span>.
            </h2>
            <div className="mt-9 grid gap-4 md:grid-cols-3">
              {STEPS.map((step) => (
                <article key={step.n} className="rounded-2xl border border-neutral-800 bg-neutral-900 p-6">
                  <span className="font-jetbrains text-xs font-bold tracking-[0.1em] text-amber-400">{step.n}</span>
                  <h3 className="mt-3 font-syne text-xl font-bold">{step.title}</h3>
                  <p className="mt-2 text-[15px] text-neutral-400">{step.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="border-t border-neutral-900 px-4 py-20 sm:px-8 xl:px-16">
          <div className="mx-auto max-w-[1200px]">
            <p className="font-jetbrains text-xs uppercase tracking-[0.14em] text-amber-400">Inside the editor</p>
            <h2 className="mt-2 font-syne text-3xl font-extrabold tracking-[-0.03em] sm:text-[44px]">
              Everything you need, in <span className="text-amber-500">one place</span>.
            </h2>
            <div className="mt-9 grid overflow-hidden rounded-2xl border border-neutral-800 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map((feature) => (
                <div key={feature.title} className="border-b border-r border-neutral-800 p-6">
                  <span className="font-jetbrains text-[11px] font-bold uppercase tracking-[0.1em] text-neutral-500">{feature.tag}</span>
                  <h3 className="mt-2 font-syne text-lg font-bold">{feature.title}</h3>
                  <p className="mt-1.5 text-[15px] text-neutral-400">{feature.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-t border-neutral-900 px-4 py-20 sm:px-8 xl:px-16">
          <div className="mx-auto grid max-w-[1200px] gap-10 md:grid-cols-[280px_1fr]">
            <h2 className="font-syne text-3xl font-extrabold tracking-[-0.03em]">Questions</h2>
            <div>
              {FAQS.map((faq) => (
                <details key={faq.q} className="border-b border-neutral-800 py-4">
                  <summary className="cursor-pointer font-semibold">{faq.q}</summary>
                  <p className="mt-2 text-[15px] text-neutral-400">{faq.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="border-t border-neutral-900 bg-[radial-gradient(60%_80%_at_50%_100%,rgba(245,158,11,0.12),transparent_70%)] px-4 py-28 text-center">
          <p className="font-jetbrains text-xs uppercase tracking-[0.14em] text-amber-400">Clipnera Editor</p>
          <h2 className="mt-3 font-syne text-4xl font-extrabold tracking-[-0.03em] sm:text-5xl">Start with one sentence.</h2>
          <button
            type="button"
            onClick={() => start('')}
            className="mt-7 h-11 rounded-xl bg-amber-500 px-6 text-sm font-bold text-neutral-950 hover:bg-amber-400"
          >
            Open the editor
          </button>
        </section>
      </main>

      <Footer onLaunchApp={() => start('')} onOpenAuthModal={() => setSignInOpen(true)} />
    </div>
  );
}
