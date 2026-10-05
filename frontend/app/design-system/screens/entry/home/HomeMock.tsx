'use client';

import { ArrowRight, CalendarClock, CircleAlert, Pencil, Play, Sparkles, Upload, X } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, cardLinkOverlay } from '@/components/ui/Card';
import { Chip } from '@/components/ui/Chip';
import type { PromptContext } from '@/components/ui/ContextChip';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconButton } from '@/components/ui/IconButton';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { PromptBar, type PromptMode } from '@/components/ui/PromptBar';
import { Skeleton, SkeletonGroup } from '@/components/ui/Skeleton';
import { WorkingText } from '@/components/ui/WorkingText';
import { cx, focusRing } from '@/lib/design/styles';

import { AppShell, LiveStatus } from '../_mock/AppShell';
import { ENTRY_BASE, jobs, projects, suggestions, topClips, user } from '../_mock/data';
import { ScreenFrame } from '../_mock/ScreenFrame';
import { Poster } from '../_mock/StandIns';
import { SCREENS } from '../_mock/states';

const SAMPLE_SOURCE: PromptContext = {
  id: 'src',
  kind: 'asset',
  label: 'Episode 41 — Why we stopped chasing views',
  meta: '58:12',
};

const YOUTUBE = /(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/\S+/i;

/**
 * Hides the Edit/Ask/Plan switch, standing in for the proposed
 * `PromptBar modes={[]}` (design-system addition DS-9): Home has no project yet.
 */
const HIDE_MODES = '[&_[role=radiogroup]]:hidden';

export function HomeMock({ state, theme }: { state: string; theme?: string }) {
  const router = useRouter();
  const firstRun = state === 'first-run';
  const startsAttached = state === 'attached' || state === 'restored' || state === 'out-of-credits';
  const [value, setValue] = useState(
    state === 'restored' ? 'Find the 5 best moments, under 45 seconds, Hinglish captions' : state === 'attached' || state === 'out-of-credits' ? 'Find the 5 best moments' : '',
  );
  const [source, setSource] = useState<PromptContext | null>(startsAttached ? SAMPLE_SOURCE : null);
  const [mode, setMode] = useState<PromptMode>('edit');
  const [needVideo, setNeedVideo] = useState(false);
  const [restoredNote, setRestoredNote] = useState(state === 'restored');
  const loading = state === 'loading';
  const offline = state === 'offline';
  const chips = firstRun || !source ? suggestions.noVideo : suggestions.withVideo;

  const onValueChange = (next: string) => {
    const link = next.match(YOUTUBE);
    if (link) {
      setSource({ ...SAMPLE_SOURCE, id: 'yt' });
      setValue(next.replace(link[0], '').trimStart());
    } else {
      setValue(next);
    }
    setNeedVideo(false);
  };

  const send = () => {
    if (!source) {
      setNeedVideo(true);
      return;
    }
    router.push(`${ENTRY_BASE}/upload?state=link${theme === 'light' ? '&theme=light' : ''}`);
  };

  const greeting = firstRun ? `Welcome to Clipnera, ${user.firstName}` : `Good evening, ${user.firstName}`;

  return (
    <ScreenFrame
      screen={SCREENS.home.title}
      states={SCREENS.home.states}
      state={state}
      theme={theme}
      note="Try it: paste any youtube.com link into the bar (it becomes the video chip), click a suggestion (it fills, never sends), press send with and without a video."
    >
      <AppShell active="home" crumbs={[{ label: 'Home' }]} hidePromptEntry offline={offline} jobs={firstRun ? [] : jobs}>
        <section aria-labelledby="home-title" className="mx-auto flex max-w-3xl flex-col items-center gap-5 pb-10 pt-6 text-center sm:pt-12">
          <p className="text-cn-label text-cn-fg-secondary">{greeting}</p>
          <h1 id="home-title" className="text-cn-display-sm font-bold text-cn-fg md:text-cn-display">
            What should we cut today?
          </h1>
          {firstRun && (
            <p className="max-w-xl text-cn-body-lg text-cn-fg-secondary">
              Paste a YouTube link or add a video, say what you want, and Clipnera finds the moments worth posting. You have 20 free credits,
              about 10 minutes of video.
            </p>
          )}

          <div className="w-full text-left">
            {restoredNote && (
              <div role="status" className="mb-2 flex items-center gap-2 rounded-cn-md border border-cn-border bg-cn-surface px-3 py-2 text-cn-label text-cn-fg-secondary">
                <Sparkles aria-hidden className="size-4 shrink-0 text-cn-accent-text" />
                <span className="flex-1">Kept from before you signed in. Nothing runs until you press send.</span>
                <IconButton label="Dismiss" icon={<X />} size="sm" onClick={() => setRestoredNote(false)} />
              </div>
            )}
            <PromptBar
              size="hero"
              value={value}
              onValueChange={onValueChange}
              onSubmit={send}
              mode={mode}
              onModeChange={setMode}
              contexts={source ? [source] : []}
              onRemoveContext={() => setSource(null)}
              onAttach={() => setSource(SAMPLE_SOURCE)}
              creditCost={source && !offline ? 116 : undefined}
              disabled={offline}
              label="Describe the clips you want"
              placeholder={source ? 'What should Clipnera make from this video?' : 'Paste a YouTube link or add a video, then say what you want'}
              className={HIDE_MODES}
            />
            {needVideo && (
              <p role="alert" className="mt-2 flex items-center gap-1.5 text-cn-label text-cn-danger-text">
                <CircleAlert aria-hidden className="size-4" />
                Add a video or paste a YouTube link first. Clipnera works from your footage.
              </p>
            )}
            {state === 'out-of-credits' && (
              <div role="alert" className="mt-2 flex flex-wrap items-center gap-3 rounded-cn-md border border-cn-danger/30 bg-cn-danger-subtle px-3 py-2">
                <p className="flex-1 text-cn-label text-cn-danger-text">
                  This 58-minute video needs about 116 credits; you have 6. Your prompt and video stay here.
                </p>
                <Button size="sm" variant="secondary">
                  Add credits
                </Button>
              </div>
            )}
            {offline && (
              <p className="mt-2 text-cn-label text-cn-fg-muted">You’re offline. Your prompt is kept; send it when you’re back.</p>
            )}
          </div>

          <div className="flex flex-wrap justify-center gap-2" role="group" aria-label="Suggestions">
            {chips.map((chip) => (
              <Chip key={chip} onClick={() => setValue(chip)} disabled={offline}>
                {chip}
              </Chip>
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-center gap-2 text-cn-label text-cn-fg-muted">
            <Button variant="ghost" size="sm" leadingIcon={<Upload />} onClick={() => setSource(SAMPLE_SOURCE)}>
              Upload a video
            </Button>
            {firstRun && (
              <Button variant="ghost" size="sm" leadingIcon={<Play />}>
                Try a sample video, free
              </Button>
            )}
          </div>
        </section>

        {firstRun ? (
          <FirstRunBelow />
        ) : (
          <div className="flex flex-col gap-10">
            <InProgress loading={loading} />
            <RecentProjects loading={loading} failed={state === 'partial'} />
            <TopClips loading={loading} />
          </div>
        )}
      </AppShell>
    </ScreenFrame>
  );
}

function SectionHeading({ id, title, link }: { id: string; title: string; link?: { label: string; href: string } }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <h2 id={id} className="text-cn-title font-semibold text-cn-fg">
        {title}
      </h2>
      {link && (
        <Link href={link.href} className={cx('inline-flex items-center gap-1 rounded-cn-xs text-cn-label text-cn-accent-text hover:underline', focusRing)}>
          {link.label}
          <ArrowRight aria-hidden className="size-3.5" />
        </Link>
      )}
    </div>
  );
}

function InProgress({ loading }: { loading: boolean }) {
  if (loading) return null;
  return (
    <section aria-labelledby="in-progress">
      <SectionHeading id="in-progress" title="In progress" />
      <ul className="grid gap-3 md:grid-cols-2">
        {jobs.map((job) => (
          <li key={job.id}>
            <Card interactive className="flex flex-col gap-2">
              <Link href={`${ENTRY_BASE}/progress?state=running`} className={cx(cardLinkOverlay, 'truncate text-cn-body font-semibold text-cn-fg')}>
                {job.project}
              </Link>
              <WorkingText className="text-cn-label">{job.label}</WorkingText>
              <ProgressBar label={`${job.project} progress`} value={job.percent} hideLabel size="sm" />
            </Card>
          </li>
        ))}
      </ul>
    </section>
  );
}

function RecentProjects({ loading, failed }: { loading: boolean; failed: boolean }) {
  const link = { label: 'All projects', href: `${ENTRY_BASE}/projects` };
  if (loading) {
    return (
      <section aria-labelledby="recent">
        <SectionHeading id="recent" title="Recent projects" link={link} />
        <SkeletonGroup label="Loading your projects" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((index) => (
            <div key={index} className="flex flex-col gap-2">
              <Skeleton className="aspect-video w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))}
        </SkeletonGroup>
      </section>
    );
  }
  if (failed) {
    return (
      <section aria-labelledby="recent">
        <SectionHeading id="recent" title="Recent projects" link={link} />
        <Card>
          <EmptyState
            size="compact"
            level={3}
            icon={<CircleAlert />}
            title="I couldn’t load your projects"
            description="Your projects are safe. Everything above still works."
            action={
              <Button size="sm" variant="secondary">
                Try again
              </Button>
            }
          />
        </Card>
      </section>
    );
  }
  return (
    <section aria-labelledby="recent">
      <SectionHeading id="recent" title="Recent projects" link={link} />
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {projects.slice(2, 5).map((project) => (
          <li key={project.id}>
            <Card interactive padding="sm" className="flex h-full flex-col gap-2.5">
              <Poster duration={project.duration} dim={project.state === 'failed'} />
              <Link href="#project" className={cx(cardLinkOverlay, 'line-clamp-2 text-cn-body font-semibold text-cn-fg')}>
                {project.title}
              </Link>
              <div className="mt-auto flex flex-wrap items-center gap-2">
                <LiveStatus state={project.state} step={project.step} />
                <span className="text-cn-caption text-cn-fg-muted">
                  {project.clips ? `${project.clips} clips · ` : ''}
                  {project.updated}
                </span>
              </div>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  );
}

function TopClips({ loading }: { loading: boolean }) {
  if (loading) return null;
  return (
    <section aria-labelledby="top-clips">
      <SectionHeading id="top-clips" title="Top clips this week" />
      <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {topClips.map((clip) => (
          <li key={clip.id}>
            <Card interactive padding="none" className="flex flex-col overflow-hidden">
              <Poster portrait duration={clip.length} className="rounded-none">
                <Badge tone="accent" className="absolute left-1.5 top-1.5">
                  Score {clip.score}
                </Badge>
              </Poster>
              <div className="flex flex-col gap-1 p-2.5">
                <Link href="#clip" className={cx(cardLinkOverlay, 'line-clamp-2 text-cn-label font-semibold text-cn-fg')}>
                  {clip.title}
                </Link>
                <span className="truncate text-cn-caption text-cn-fg-muted">{clip.project}</span>
                <div className="relative z-cn-raised mt-1 flex gap-1">
                  <IconButton label={`Edit ${clip.title}`} icon={<Pencil />} size="sm" variant="secondary" />
                  <IconButton label={`Schedule ${clip.title}`} icon={<CalendarClock />} size="sm" variant="secondary" />
                </div>
              </div>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  );
}

function FirstRunBelow() {
  const steps = [
    { label: 'Make your first clips', done: false, action: 'Add a video' },
    { label: 'Connect YouTube or Instagram', done: false, action: 'Connect' },
    { label: 'Set your brand colours and logo', done: false, action: 'Open brand kit' },
    { label: 'Schedule or publish a clip', done: false, action: 'Open scheduler' },
  ];
  return (
    <section aria-labelledby="setup" className="mx-auto max-w-3xl">
      <Card padding="lg" className="flex flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <h2 id="setup" className="text-cn-title-sm font-semibold">
              Get set up
            </h2>
            <p className="text-cn-body text-cn-fg-secondary">Four things that make your clips feel like yours. Do them in any order.</p>
          </div>
          <IconButton label="Hide set-up list" icon={<X />} size="sm" />
        </div>
        <ProgressBar label="Set-up progress" value={0} max={4} valueText="0 of 4 done" />
        <ul className="flex flex-col divide-y divide-cn-border">
          {steps.map((step) => (
            <li key={step.label} className="flex items-center justify-between gap-3 py-2.5">
              <span className="text-cn-body text-cn-fg">{step.label}</span>
              <Button size="sm" variant="ghost">
                {step.action}
              </Button>
            </li>
          ))}
        </ul>
      </Card>
    </section>
  );
}
