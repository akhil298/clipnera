import React from 'react';
import Link from 'next/link';
import { CalendarDays, Captions, Film, Scissors } from 'lucide-react';

interface AuthShellProps {
  mode: 'login' | 'register';
  children: React.ReactNode;
}

/** Three sample clips for the showcase; styled frames, no real footage or people. */
const SAMPLE_CLIPS = [
  { caption: ['MOST STARTUPS', 'NEVER', 'MAKE IT'], score: 94, tone: 'from-orange-400 via-rose-500 to-violet-600', offset: '' },
  { caption: ['THE', '3AM', 'ROUTINE'], score: 87, tone: 'from-sky-500 via-teal-500 to-emerald-500', offset: 'mt-10' },
  { caption: ['ONE HABIT,', 'DOUBLE', 'FOCUS'], score: 80, tone: 'from-pink-500 via-amber-500 to-orange-400', offset: 'mt-4' },
];

const POINTS = [
  { icon: Scissors, text: 'Finds the moments worth posting in long videos' },
  { icon: Captions, text: 'Adds captions, hooks and B-roll in your brand style' },
  { icon: CalendarDays, text: 'Publishes and schedules to YouTube, Instagram and TikTok' },
];

/**
 * Sign-in and sign-up: what Clipnera makes on one side, the Google button on
 * the other. Stacks on phones with the form first.
 */
export function AuthShell({ mode, children }: AuthShellProps) {
  return (
    <div className="min-h-[100dvh] grid lg:grid-cols-[1.1fr_1fr] bg-neutral-950 text-neutral-100">
      {/* Showcase */}
      <aside className="relative overflow-hidden order-2 lg:order-1 border-t lg:border-t-0 lg:border-r border-neutral-800 bg-[radial-gradient(70%_60%_at_20%_20%,rgba(245,158,11,0.16),transparent_60%),radial-gradient(60%_60%_at_90%_100%,rgba(139,92,246,0.14),transparent_60%)] px-6 py-10 sm:px-10 lg:p-12 flex flex-col gap-10">
        <Link href="/" className="hidden lg:flex items-center gap-2.5 w-fit">
          <span className="flex items-center justify-center w-9 h-9 rounded-[11px] bg-gradient-to-br from-amber-300 via-amber-500 to-amber-600 text-neutral-950">
            <Film className="w-[18px] h-[18px] stroke-[2.4]" />
          </span>
          <span className="font-extrabold text-lg tracking-tight">
            Clip<span className="text-amber-400">nera</span>
          </span>
        </Link>

        <div className="flex gap-3 sm:gap-4 justify-center lg:justify-start -rotate-3" aria-hidden="true">
          {SAMPLE_CLIPS.map((clip) => (
            <div
              key={clip.score}
              className={`relative w-24 sm:w-32 aspect-[9/16] rounded-2xl overflow-hidden bg-gradient-to-br ${clip.tone} shadow-2xl shadow-black/60 ${clip.offset}`}
            >
              <div className="absolute left-1/2 top-[30%] -translate-x-1/2 w-[46%] aspect-square rounded-full bg-black/25" />
              <div className="absolute left-1/2 top-[52%] -translate-x-1/2 w-[64%] h-[48%] rounded-t-[45%] bg-black/25" />
              <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/70 to-transparent" />
              <span className="absolute top-2 right-2 w-8 h-8 rounded-full bg-black/60 border-2 border-amber-400 flex items-center justify-center text-[10px] font-extrabold text-amber-200">
                {clip.score}
              </span>
              <p className="absolute inset-x-2 bottom-[16%] text-center font-['Anton',Impact,sans-serif] text-[13px] sm:text-[15px] leading-[1.05] text-white [text-shadow:0_2px_0_#000]">
                {clip.caption[0]} <span className="text-yellow-300">{clip.caption[1]}</span> {clip.caption[2]}
              </p>
            </div>
          ))}
        </div>

        <div className="space-y-5 max-w-md">
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight leading-[1.05] text-balance">
            Long videos in. <span className="text-amber-400 whitespace-nowrap">Scroll&#8209;stopping</span> clips out.
          </h1>
          <ul className="space-y-3">
            {POINTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 text-sm text-neutral-300">
                <span className="w-7 h-7 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center shrink-0">
                  <Icon className="w-4 h-4" />
                </span>
                <span className="pt-1">{text}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      {/* Form */}
      <main className="order-1 lg:order-2 flex flex-col items-center justify-center px-4 py-12 sm:px-8">
        <div className="w-full max-w-sm space-y-5">
          <Link href="/" className="lg:hidden flex items-center justify-center gap-2.5">
            <span className="flex items-center justify-center w-9 h-9 rounded-[11px] bg-gradient-to-br from-amber-300 via-amber-500 to-amber-600 text-neutral-950">
              <Film className="w-[18px] h-[18px] stroke-[2.4]" />
            </span>
            <span className="font-extrabold text-lg tracking-tight">
              Clip<span className="text-amber-400">nera</span>
            </span>
          </Link>
          {children}
          <p className="text-center text-xs text-neutral-400">
            {mode === 'login' ? (
              <>
                New to Clipnera?{' '}
                <Link href="/signup" className="font-semibold text-amber-300 hover:text-amber-200">
                  Create an account
                </Link>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <Link href="/login" className="font-semibold text-amber-300 hover:text-amber-200">
                  Sign in
                </Link>
              </>
            )}
          </p>
          <nav aria-label="Legal" className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-[11px] text-neutral-500">
            <Link href="/privacy" className="hover:text-neutral-300">Privacy</Link>
            <Link href="/terms" className="hover:text-neutral-300">Terms</Link>
            <Link href="/refunds" className="hover:text-neutral-300">Refunds</Link>
            <Link href="/cookies" className="hover:text-neutral-300">Cookies</Link>
          </nav>
        </div>
      </main>
    </div>
  );
}
