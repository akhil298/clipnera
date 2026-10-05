'use client';

import {
  AudioLines,
  Captions,
  ChevronDown,
  CircleAlert,
  Crop,
  Film,
  Instagram,
  Menu as MenuIcon,
  RotateCcw,
  Scissors,
  Sparkles,
  Youtube,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useRef, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button, buttonClasses } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { Chip } from '@/components/ui/Chip';
import type { PromptContext } from '@/components/ui/ContextChip';
import { Dialog } from '@/components/ui/Dialog';
import { Drawer } from '@/components/ui/Drawer';
import { IconButton } from '@/components/ui/IconButton';
import { PromptBar, type PromptMode } from '@/components/ui/PromptBar';
import { Skeleton } from '@/components/ui/Skeleton';
import { cx, focusRing } from '@/lib/design/styles';

import { ENTRY_BASE, suggestions } from '../_mock/data';
import { ScreenFrame } from '../_mock/ScreenFrame';
import { SignInPanel } from '../_mock/SignInPanel';
import { Poster, Wordmark } from '../_mock/StandIns';
import { SCREENS } from '../_mock/states';

const NAV_LINKS = [
  ['How it works', '#how-it-works'],
  ['Captions', '#captions'],
  ['Editing', '#editing'],
  ['Pricing', '#pricing'],
  ['FAQ', '#faq'],
] as const;

const HIDE_MODES = '[&_[role=radiogroup]]:hidden';
const YOUTUBE = /(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/\S+/i;
const SOURCE: PromptContext = { id: 'src', kind: 'asset', label: 'Episode 41 — Why we stopped chasing views', meta: '58:12' };

const ENGINE = [
  { icon: <AudioLines />, step: 'Listen', title: 'Every word, timestamped', body: 'A transcript with timings for every word, in English, Hindi, Telugu, Hinglish or Tenglish.' },
  { icon: <Sparkles />, step: 'Score', title: 'Moments ranked 0–100', body: 'Hooks, stories and takeaways scored so you start with the strongest. Scores help you choose; they don’t predict views.' },
  { icon: <Crop />, step: 'Reframe', title: 'The frame follows the face', body: '16:9 to 9:16 around whoever is speaking.' },
  { icon: <AudioLines />, step: 'Clean audio', title: 'Hum out, voice in', body: 'Echo, hiss and fan hum reduced. Works best on steady noise.' },
  { icon: <Captions />, step: 'Caption', title: 'Word by word, burned in', body: '21 caption styles; change colours, casing and lines.' },
  { icon: <Film />, step: 'B-roll', title: 'Cutaways where they fit', body: 'Licensed footage dropped in where it helps the story.' },
];

const FAQS = [
  ['How does Clipnera choose the moments?', 'It transcribes your video, then looks for strong hooks, emotional moments, useful takeaways and shareable lines, and scores each out of 100. Scores help you choose; they don’t predict views.'],
  ['What can I upload?', 'A YouTube link, or an MP4, MOV, WebM or MKV file. Free takes videos up to 30 minutes; Pro takes longer ones.'],
  ['Can I edit the clips myself?', 'Yes. Trim, change captions and reframe by hand, or describe the change in a sentence. Every change can be undone.'],
  ['Which languages work?', 'Prompts in English or Hinglish. Captions in English, Hindi, Telugu, Hinglish and Tenglish.'],
  ['What does background noise reduction do?', 'It reduces steady noise such as fan or air-conditioner hum, electrical hum and room echo. It can’t fully remove loud or overlapping sounds.'],
  ['Where can I publish?', 'Straight to YouTube Shorts and Instagram Reels, or download the MP4 for anywhere else. Titles and hashtags are suggested, and you edit them before posting.'],
  ['Is the music and B-roll safe to post?', 'Yes. Both come from libraries licensed for commercial use, and each export lists any credit a track needs.'],
];

export function LandingMock({ state, theme }: { state: string; theme?: string }) {
  const router = useRouter();
  const signedIn = state === 'signed-in';
  const heroRef = useRef<HTMLTextAreaElement>(null);
  const [value, setValue] = useState(state === 'typed' || state === 'sign-in' ? 'Find the 5 best moments, under 45 seconds' : state === 'bad-link' ? 'vimeo.com/81723' : '');
  const [source, setSource] = useState<PromptContext | null>(state === 'typed' || state === 'sign-in' ? SOURCE : null);
  const [mode, setMode] = useState<PromptMode>('edit');
  const [signInOpen, setSignInOpen] = useState(state === 'sign-in');
  const [menuOpen, setMenuOpen] = useState(state === 'menu');

  const onValueChange = (next: string) => {
    const link = next.match(YOUTUBE);
    if (link) {
      setSource(SOURCE);
      setValue(next.replace(link[0], '').trimStart());
    } else setValue(next);
  };

  const send = () => {
    if (signedIn) router.push(`${ENTRY_BASE}/home?state=restored${theme === 'light' ? '&theme=light' : ''}`);
    else setSignInOpen(true);
  };

  return (
    <ScreenFrame
      screen={SCREENS.landing.title}
      states={SCREENS.landing.states}
      state={state}
      theme={theme}
      note="Merges / and /editor. The hero is the product: paste a YouTube link (it becomes a chip), type, press send. Signed out opens sign-in and keeps everything; signed in goes to Home with it restored."
    >
      <a href="#landing-main" className="fixed left-4 top-2 z-cn-skiplink -translate-y-16 rounded-cn-md bg-cn-accent px-3 py-2 text-cn-label font-semibold text-cn-accent-fg focus:translate-y-0">
        Skip to content
      </a>
      <header className="sticky top-0 z-cn-sticky border-b border-cn-border bg-cn-bg/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-screen-2xl items-center gap-6 px-4 sm:px-8">
          <Link href="#top" aria-label="Clipnera, back to top" className={cx('rounded-cn-sm', focusRing)}>
            <Wordmark />
          </Link>
          <nav aria-label="Sections" className="hidden flex-1 justify-center md:flex">
            <ul className="flex gap-1">
              {NAV_LINKS.map(([label, href]) => (
                <li key={href}>
                  <a href={href} className={buttonClasses({ variant: 'ghost', size: 'sm' })}>
                    {label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          <span className="flex-1 md:hidden" />
          <div className="flex items-center gap-2">
            {signedIn ? (
              <Link href={`${ENTRY_BASE}/home`} className={buttonClasses({ variant: 'secondary', size: 'sm' })}>
                Open Clipnera
              </Link>
            ) : (
              <>
                <Button variant="ghost" size="sm" className="hidden sm:inline-flex" onClick={() => setSignInOpen(true)}>
                  Sign in
                </Button>
                <Button variant="secondary" size="sm" onClick={() => heroRef.current?.focus()}>
                  Start free
                </Button>
              </>
            )}
            <IconButton label="Menu" icon={<MenuIcon />} className="md:hidden" onClick={() => setMenuOpen(true)} />
          </div>
        </div>
      </header>

      <main id="landing-main">
        <section id="top" aria-labelledby="hero-title" className="mx-auto flex max-w-4xl flex-col items-center gap-6 px-4 pb-16 pt-16 text-center sm:pt-24">
          <h1 id="hero-title" className="font-cn-display text-cn-display-sm font-bold sm:text-cn-display lg:text-cn-display-lg">
            Long video in.
            <br />
            <span className="text-cn-accent-text">Shorts</span> out.
          </h1>
          <p className="max-w-2xl text-cn-body-lg text-cn-fg-secondary">
            Paste a YouTube link or add a video and say what you want. Clipnera finds the moments worth posting, reframes them to 9:16 around the speaker,
            cleans the audio and adds captions. You review before anything is posted.
          </p>
          <div className="w-full max-w-3xl text-left">
            <PromptBar
              ref={heroRef}
              size="hero"
              value={value}
              onValueChange={onValueChange}
              onSubmit={send}
              mode={mode}
              onModeChange={setMode}
              contexts={source ? [source] : []}
              onRemoveContext={() => setSource(null)}
              onAttach={() => setSource(SOURCE)}
              label="Paste a YouTube link or describe the clips you want"
              placeholder="Paste a YouTube link or add a video, then say what you want"
              className={HIDE_MODES}
            />
            {state === 'bad-link' && (
              <p role="alert" className="mt-2 flex items-start gap-1.5 text-cn-label text-cn-danger-text">
                <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
                That isn’t a YouTube link. Paste a youtube.com or youtu.be address, or add the video file with the paperclip.
              </p>
            )}
          </div>
          <div role="group" aria-label="Suggestions" className="flex flex-wrap justify-center gap-2">
            {suggestions.noVideo.map((chip) => (
              <Chip key={chip} onClick={() => setValue(chip)}>
                {chip}
              </Chip>
            ))}
          </div>
          <p className="text-cn-label text-cn-fg-muted">Free plan, no card · 20 free credits every 30 days · Only YouTube and Instagram for direct posting</p>
        </section>

        <section aria-labelledby="example-title" className="mx-auto max-w-screen-xl px-4 pb-20 sm:px-8">
          <Card padding="lg" className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <h2 id="example-title" className="text-cn-title-sm font-semibold">
                One 58-minute podcast, three clips
              </h2>
              <Badge>Example output</Badge>
            </div>
            <div className="grid items-center gap-6 lg:grid-cols-5">
              <Poster duration="58:12" className="lg:col-span-3" />
              <ul className="grid grid-cols-3 gap-3 lg:col-span-2">
                {[94, 88, 81].map((score, index) => (
                  <li key={score}>
                    <Poster portrait duration={`0:${41 - index * 3}`}>
                      <Badge tone="accent" className="absolute left-1.5 top-1.5">
                        {score}
                      </Badge>
                    </Poster>
                  </li>
                ))}
              </ul>
            </div>
            <p className="text-cn-caption text-cn-fg-muted">Sample clips for illustration. Your clips come from your own footage; scores help you choose and don’t predict views.</p>
          </Card>
        </section>

        <section id="how-it-works" aria-labelledby="how-title" className="mx-auto max-w-screen-xl px-4 pb-20 sm:px-8">
          <h2 id="how-title" className="font-cn-display text-cn-display-sm font-bold">
            Six editing jobs, done for you
          </h2>
          <p className="mt-2 max-w-2xl text-cn-body-lg text-cn-fg-secondary">Each card is a real step your video goes through, in order, with you in control at the end.</p>
          <ul className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {ENGINE.map((item) => (
              <li key={item.title}>
                <Card padding="lg" className="flex h-full flex-col gap-3">
                  <Skeleton className="h-32 w-full motion-safe:animate-none" />
                  <span className="inline-flex items-center gap-2 text-cn-caption text-cn-fg-muted [&_svg]:size-4">
                    {item.icon}
                    {item.step}
                  </span>
                  <h3 className="text-cn-title-sm font-semibold">{item.title}</h3>
                  <p className="text-cn-body text-cn-fg-secondary">{item.body}</p>
                </Card>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-cn-caption text-cn-fg-muted">Grey tiles stand for the existing EngineSection visuals, kept and restyled.</p>
        </section>

        <section id="captions" aria-labelledby="captions-title" className="mx-auto grid max-w-screen-xl gap-4 px-4 pb-20 sm:px-8 lg:grid-cols-2">
          <h2 id="captions-title" className="sr-only">
            Before and after, and captions
          </h2>
          <Card padding="lg">
            <CardHeader title="Drag the line. That’s the whole edit." description="BeforeAfterShowcase, kept as built (accessible slider), restyled to tokens." />
            <Poster portrait className="mx-auto mt-4 w-48" />
          </Card>
          <Card padding="lg">
            <CardHeader title="Captions people actually read" description="CaptionTypographyShowcase, kept: the real presets and live preview." />
            <div className="mt-4 flex flex-wrap gap-2">
              {['Karaoke', 'Bold pop', 'Glitch', 'Blur in'].map((name, index) => (
                <Chip key={name} selected={index === 0}>
                  {name}
                </Chip>
              ))}
            </div>
          </Card>
        </section>

        <section id="editing" aria-labelledby="editing-title" className="border-y border-cn-border bg-cn-surface">
          <div className="mx-auto grid max-w-screen-xl gap-10 px-4 py-20 sm:px-8 lg:grid-cols-2">
            <div className="flex flex-col gap-4">
              <h2 id="editing-title" className="font-cn-display text-cn-display-sm font-bold">
                Then change anything with a sentence
              </h2>
              <p className="text-cn-body-lg text-cn-fg-secondary">
                Select a clip or a few words and say what you want: shorter, a new hook, Hinglish captions, B-roll here. Each prompt becomes one version
                you can undo.
              </p>
              <ol className="flex flex-col gap-3">
                {[
                  ['Drop and describe', 'Add footage or a link and say what you want.'],
                  ['Direct the edit', 'Point at a clip or a line, then prompt. Or trim by hand.'],
                  ['Export or post', 'Download the MP4, or post to YouTube and Instagram.'],
                ].map(([title, body], index) => (
                  <li key={title} className="flex gap-3">
                    <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-cn-full border border-cn-border-strong font-cn-mono text-cn-caption">{index + 1}</span>
                    <span>
                      <span className="block text-cn-body font-semibold">{title}</span>
                      <span className="block text-cn-body text-cn-fg-secondary">{body}</span>
                    </span>
                  </li>
                ))}
              </ol>
            </div>
            <div className="flex flex-col justify-center gap-3" aria-label="Example of an editing prompt" role="group">
              <Poster portrait className="mx-auto w-40" duration="0:41" />
              <PromptBar
                value="Make the hook punchier and add Hinglish captions"
                onValueChange={() => undefined}
                onSubmit={() => undefined}
                mode="edit"
                onModeChange={() => undefined}
                contexts={[{ id: 'c', kind: 'clip', label: 'The day I stopped chasing views', meta: '0:41' }]}
                creditCost={4}
                label="Example editing prompt"
              />
            </div>
          </div>
        </section>

        <section aria-labelledby="publish-title" className="mx-auto max-w-screen-xl px-4 py-20 sm:px-8">
          <h2 id="publish-title" className="font-cn-display text-cn-display-sm font-bold">
            Straight to where people scroll
          </h2>
          <ul className="mt-8 grid gap-4 sm:grid-cols-3">
            {[
              [<Youtube key="y" />, 'YouTube Shorts', 'Publish now or schedule'],
              [<Instagram key="i" />, 'Instagram Reels', 'Publish now or schedule, with a cover'],
              [<Film key="f" />, 'Anywhere else', 'Download the MP4'],
            ].map(([icon, title, body]) => (
              <li key={String(title)}>
                <Card className="flex items-center gap-3">
                  <span aria-hidden className="inline-flex text-cn-fg-secondary [&_svg]:size-6">
                    {icon}
                  </span>
                  <span>
                    <span className="block text-cn-body font-semibold">{title}</span>
                    <span className="block text-cn-label text-cn-fg-secondary">{body}</span>
                  </span>
                </Card>
              </li>
            ))}
          </ul>
        </section>

        <section id="pricing" aria-labelledby="pricing-title" className="mx-auto max-w-4xl px-4 pb-20 sm:px-8">
          <h2 id="pricing-title" className="text-center font-cn-display text-cn-display-sm font-bold">
            Start free. Upgrade when it’s working.
          </h2>
          <p className="mx-auto mt-2 max-w-2xl text-center text-cn-body text-cn-fg-secondary">
            Prices in Indian rupees; the amount shown is the amount you pay. Pro doesn’t renew on its own.
          </p>
          {state === 'pricing-error' ? (
            <Card className="mt-8 flex flex-wrap items-center gap-3" role="alert">
              <CircleAlert aria-hidden className="size-5 text-cn-danger-text" />
              <p className="flex-1 text-cn-body text-cn-fg-secondary">Prices didn’t load. The Free plan needs no card, so you can start now either way.</p>
              <Button variant="secondary" size="sm" leadingIcon={<RotateCcw />}>
                Try again
              </Button>
            </Card>
          ) : (
            <ul className="mt-8 grid gap-4 md:grid-cols-2">
              {[
                ['Free', '₹0', ['20 credits every 30 days', 'Videos up to 30 min', '9:16 clips with captions']],
                ['Pro', 'Price from the server', ['1,500 credits a month', 'Longer videos, every format', 'Brand kit, channel intro, scheduling']],
              ].map(([name, price, rows], index) => (
                <li key={String(name)}>
                  <Card padding="lg" selected={index === 1} className="flex h-full flex-col gap-4">
                    <CardHeader title={String(name)} description={<span className="font-cn-mono text-cn-title text-cn-fg">{String(price)}</span>} />
                    <ul className="flex flex-col gap-1.5 text-cn-body text-cn-fg-secondary">
                      {(rows as string[]).map((row) => (
                        <li key={row}>{row}</li>
                      ))}
                    </ul>
                    <Button variant={index === 1 ? 'primary' : 'secondary'} className="mt-auto">
                      {index === 1 ? 'Get Pro' : 'Start free'}
                    </Button>
                  </Card>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-3 text-center text-cn-caption text-cn-fg-muted">Sample prices; the real cards read the plans from the server. Credit packs never expire.</p>
        </section>

        <section id="faq" aria-labelledby="faq-title" className="mx-auto max-w-3xl px-4 pb-20 sm:px-8">
          <h2 id="faq-title" className="font-cn-display text-cn-display-sm font-bold">
            Straight answers
          </h2>
          <div className="mt-6 divide-y divide-cn-border border-y border-cn-border">
            {FAQS.map(([q, a], index) => (
              <details key={q} open={index === 0} className="group py-4">
                <summary className={cx('flex cursor-pointer list-none items-center justify-between gap-4 rounded-cn-xs text-cn-body-lg font-semibold', focusRing)}>
                  {q}
                  <ChevronDown aria-hidden className="size-4 shrink-0 text-cn-fg-muted group-open:rotate-180 motion-safe:transition-transform motion-safe:duration-cn-base" />
                </summary>
                <p className="mt-2 text-cn-body text-cn-fg-secondary">{a}</p>
              </details>
            ))}
          </div>
        </section>

        <section aria-labelledby="cta-title" className="border-t border-cn-border bg-cn-surface">
          <div className="mx-auto flex max-w-3xl flex-col items-center gap-4 px-4 py-20 text-center">
            <h2 id="cta-title" className="font-cn-display text-cn-display-sm font-bold">
              Your next Shorts are already recorded.
            </h2>
            <Button
              size="lg"
              variant="secondary"
              leadingIcon={<Scissors />}
              onClick={() => {
                document.getElementById('top')?.scrollIntoView({ behavior: 'smooth' });
                heroRef.current?.focus({ preventScroll: true });
              }}
            >
              Start with your video
            </Button>
            <p className="text-cn-label text-cn-fg-muted">Free plan, no card needed.</p>
          </div>
        </section>
      </main>

      <footer className="border-t border-cn-border">
        <div className="mx-auto flex max-w-screen-xl flex-col gap-6 px-4 py-10 sm:px-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <Wordmark size="sm" />
            <p className="text-cn-label text-cn-fg-muted">Long video in. Shorts out.</p>
          </div>
          <nav aria-label="Legal" className="flex flex-wrap gap-x-5 gap-y-2 text-cn-label">
            {['Terms of Service', 'Privacy Policy', 'Refund Policy', 'Cookie Policy', 'Delete your data'].map((label) => (
              <a key={label} href="#legal" className={cx('rounded-cn-xs text-cn-fg-secondary hover:text-cn-fg', focusRing)}>
                {label}
              </a>
            ))}
          </nav>
          <p className="text-cn-caption text-cn-fg-muted">© 2026 Clipnera. Business details block (legal name, address, GSTIN, contact) kept word for word.</p>
        </div>
      </footer>

      <Dialog
        open={signInOpen}
        onOpenChange={setSignInOpen}
        size="sm"
        title="Sign in to start"
        description="New here? Signing in with Google creates your account."
      >
        <SignInPanel variant={source || value ? 'carried' : 'default'} inDialog />
      </Dialog>

      <Drawer open={menuOpen} onOpenChange={setMenuOpen} title="Menu" side="right" size="sm">
        <nav aria-label="Sections, phone" className="flex flex-col gap-1">
          {NAV_LINKS.map(([label, href]) => (
            <a key={href} href={href} onClick={() => setMenuOpen(false)} className={buttonClasses({ variant: 'ghost', fullWidth: true, size: 'lg' })}>
              <span className="flex-1 text-left">{label}</span>
            </a>
          ))}
          <div className="mt-4 flex flex-col gap-2 border-t border-cn-border pt-4">
            <Button variant="secondary" size="lg" fullWidth onClick={() => setSignInOpen(true)}>
              Sign in
            </Button>
          </div>
        </nav>
      </Drawer>
    </ScreenFrame>
  );
}
