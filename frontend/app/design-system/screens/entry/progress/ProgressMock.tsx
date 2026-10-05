'use client';

import { CircleAlert, Coins, Mail, RefreshCw, Youtube } from 'lucide-react';
import { type ReactNode, useEffect, useRef, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { Dialog } from '@/components/ui/Dialog';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { type ProgressStep, ProgressSteps } from '@/components/ui/ProgressSteps';
import { ResultMessage } from '@/components/ui/ResultMessage';
import { type RunStep, StepList } from '@/components/ui/StepList';
import { Switch } from '@/components/ui/Switch';
import { useToast } from '@/components/ui/Toast';
import { WorkingText } from '@/components/ui/WorkingText';

import { AppShell, LiveStatus } from '../_mock/AppShell';
import { pipelineStages } from '../_mock/data';
import { ScreenFrame } from '../_mock/ScreenFrame';
import { FolderBadge, Poster } from '../_mock/StandIns';
import { SCREENS } from '../_mock/states';

type StageStatus = ProgressStep['status'];

/** Which of the five stages is where, per state. */
const STAGE_STATE: Record<string, StageStatus[]> = {
  uploading: ['active', 'upcoming', 'upcoming', 'upcoming', 'upcoming'],
  running: ['done', 'done', 'active', 'upcoming', 'upcoming'],
  expanded: ['done', 'done', 'active', 'upcoming', 'upcoming'],
  'waiting-credits': ['done', 'upcoming', 'upcoming', 'upcoming', 'upcoming'],
  reconnecting: ['done', 'done', 'active', 'upcoming', 'upcoming'],
  failed: ['done', 'done', 'failed', 'upcoming', 'upcoming'],
  stop: ['done', 'done', 'active', 'upcoming', 'upcoming'],
  stopped: ['done', 'done', 'done', 'failed', 'upcoming'],
  done: ['done', 'done', 'done', 'done', 'done'],
};

const DONE_DETAIL = ['Got 58:12 from YouTube', 'Removed hum and room echo', '8,412 words, with timings', '23 moments scored', '9 clips at 9:16, captions on'];

/** The eleven server steps in plain words, behind "Show details" (doc §10 mapping). */
const DETAIL_STEPS: RunStep[] = [
  { id: 'download', label: 'Getting the video from YouTube', status: 'done', detail: '58:12 · 1080p' },
  { id: 'extract', label: 'Taking out the audio', status: 'done' },
  { id: 'denoise', label: 'Cleaning up the audio', status: 'done', detail: 'Studio voice at 90%' },
  { id: 'transcribe', label: 'Transcribing', status: 'active', progress: '42 of 58 min' },
  { id: 'topics', label: 'Working out the topics', status: 'queued' },
  { id: 'visual', label: 'Looking at faces and framing', status: 'queued' },
  { id: 'classify', label: 'Sorting the kind of moment', status: 'queued' },
  { id: 'highlights', label: 'Finding the best moments', status: 'queued' },
  { id: 'score', label: 'Scoring each moment', status: 'queued' },
  { id: 'titles', label: 'Writing titles and hashtags', status: 'queued' },
  { id: 'render', label: 'Making the 9:16 clips', status: 'queued' },
];

export function ProgressMock({ state, theme }: { state: string; theme?: string }) {
  const [stopOpen, setStopOpen] = useState(state === 'stop');
  const uploading = state === 'uploading';
  const statuses = STAGE_STATE[state];
  const title = uploading ? 'Masterclass: pricing your first product' : 'Episode 41 — Why we stopped chasing views';

  const steps: ProgressStep[] = pipelineStages.map((stage, index) => {
    const status = statuses[index];
    let description: ReactNode = stage.detail;
    if (status === 'done') description = DONE_DETAIL[index];
    if (status === 'failed') description = state === 'failed' ? 'I couldn’t finish the transcript.' : 'Stopped here';
    if (status === 'active') {
      description = (
        <span className="flex w-64 max-w-full flex-col gap-1.5 pt-1">
          <WorkingText>{uploading ? 'Uploading from this tab · 1.2 of 1.9 GB' : 'Transcribing · 42 of 58 min'}</WorkingText>
          <ProgressBar label={`${stage.label} progress`} value={uploading ? 62 : 72} hideLabel size="sm" />
        </span>
      );
    }
    return { id: stage.id, label: stage.label, description, status };
  });

  const liveState =
    state === 'done' ? 'ready' : state === 'failed' ? 'failed' : state === 'stopped' ? 'cancelled' : state === 'waiting-credits' ? 'awaiting_credits' : 'processing';

  const reconnecting =
    state === 'reconnecting' ? (
      <div role="status" className="flex items-center gap-2 border-t border-cn-border bg-cn-surface px-4 py-2 text-cn-label text-cn-fg-secondary sm:px-6 lg:px-8">
        <RefreshCw aria-hidden className="size-4 shrink-0" />
        <WorkingText>Reconnecting.</WorkingText> Your clips are still being made; this page catches up when the connection is back.
      </div>
    ) : undefined;

  return (
    <ScreenFrame
      screen={SCREENS.progress.title}
      states={SCREENS.progress.states}
      state={state}
      theme={theme}
      note="The same URL shows the clip list once the clips are ready (designed in screens/02). Every processing card, toast and activity row links here."
    >
      <AppShell
        active="projects"
        crumbs={[{ label: 'Projects', href: '#projects' }, { label: 'Founder Podcast · season 2', href: '#folder' }, { label: title }]}
        banner={reconnecting}
        jobs={state === 'done' || state === 'failed' || state === 'stopped' ? [] : undefined}
      >
        {state === 'done' && <ReadyToast />}
        <div className="flex flex-col gap-6">
          <header className="flex flex-col gap-2">
            <h1 className="text-cn-title-lg font-bold text-cn-fg">{title}</h1>
            <div className="flex flex-wrap items-center gap-2 text-cn-label text-cn-fg-secondary">
              <LiveStatus
                state={liveState}
                step={state === 'reconnecting' ? 'Transcribing · last update 0:40 ago' : uploading ? 'Uploading · 62%' : 'Transcribing · 72%'}
              />
              <span className="inline-flex items-center gap-1.5">
                <Youtube aria-hidden className="size-4" />
                {uploading ? 'Upload · masterclass-final.mp4' : 'YouTube · Founder Podcast'}
              </span>
              <span className="font-cn-mono text-cn-caption tabular-nums">{uploading ? '1:12:40' : '58:12'}</span>
              <FolderBadge name="Founder Podcast · season 2" />
            </div>
          </header>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="flex flex-col gap-4 lg:col-span-2">
              <StateBody state={state} onStop={() => setStopOpen(true)} />

              <Card padding="lg" className="flex flex-col gap-5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h2 className="text-cn-title-sm font-semibold">Steps</h2>
                  {(state === 'running' || state === 'expanded' || state === 'reconnecting') && (
                    <span className="text-cn-label text-cn-fg-muted">About 6 min left</span>
                  )}
                </div>
                <ProgressSteps label="Progress of this project" orientation="vertical" steps={steps} />
                {state !== 'uploading' && state !== 'waiting-credits' && (
                  <StepList
                    steps={state === 'failed' ? DETAIL_STEPS.map((s) => (s.id === 'transcribe' ? { ...s, status: 'failed', detail: 'The audio cut out at 31:08.', progress: undefined } : s)) : DETAIL_STEPS}
                    elapsed="4:12"
                    defaultExpanded={state === 'expanded'}
                    onRetryStep={state === 'failed' ? () => undefined : undefined}
                  />
                )}
              </Card>

              <section aria-labelledby="clips-preview" className="flex flex-col gap-3">
                <h2 id="clips-preview" className="text-cn-title-sm font-semibold">
                  {state === 'done' ? '9 clips' : 'Your clips appear here'}
                </h2>
                <ul className="grid grid-cols-3 gap-3 sm:grid-cols-5">
                  {[0, 1, 2, 3, 4].map((index) => (
                    <li key={index} className={index > 2 ? 'hidden sm:block' : ''}>
                      <Poster portrait dim={state !== 'done'} duration={state === 'done' ? `0:${38 + index}` : undefined} />
                    </li>
                  ))}
                </ul>
              </section>
            </div>

            <aside aria-label="What you asked for" className="flex flex-col gap-4">
              <Card>
                <CardHeader title="What you asked for" level={2} />
                <blockquote className="mt-3 border-l-2 border-cn-border-strong pl-3 text-cn-body text-cn-fg">
                  Find the 5 best moments, under 45 seconds, Hinglish captions
                </blockquote>
                <dl className="mt-4 flex flex-col gap-2 text-cn-label">
                  {[
                    ['Formats', '9:16'],
                    ['Audio', 'Studio voice, 90%'],
                    ['Captions', 'Auto (Hinglish in Roman letters)'],
                    ['Folder', 'Founder Podcast · season 2'],
                  ].map(([term, value]) => (
                    <div key={term} className="flex justify-between gap-3">
                      <dt className="text-cn-fg-muted">{term}</dt>
                      <dd className="text-right text-cn-fg">{value}</dd>
                    </div>
                  ))}
                </dl>
              </Card>
              <Card className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <Coins aria-hidden className="size-4 text-cn-fg-secondary" />
                  <span className="font-cn-mono text-cn-label tabular-nums">116 credits</span>
                  <Badge tone={state === 'failed' ? 'success' : 'neutral'}>
                    {state === 'failed' ? 'Returned' : state === 'waiting-credits' ? 'Not charged yet' : 'Charged'}
                  </Badge>
                </div>
                <p className="text-cn-caption text-cn-fg-muted">If making clips fails, the credits come back on their own.</p>
              </Card>
              {state !== 'done' && state !== 'failed' && state !== 'stopped' && (
                <Card className="flex flex-col gap-3">
                  <p className="text-cn-label text-cn-fg-secondary">
                    {uploading
                      ? 'Keep this tab open until the upload finishes. After that you can close it; the rest happens on our side.'
                      : 'You can close this tab. I’ll let you know here and by notification when the clips are ready.'}
                  </p>
                  <Switch label={<span className="inline-flex items-center gap-1.5"><Mail aria-hidden className="size-4" />Email me when it’s done</span>} defaultChecked />
                </Card>
              )}
            </aside>
          </div>
        </div>

        <Dialog
          open={stopOpen}
          onOpenChange={setStopOpen}
          role="alertdialog"
          size="sm"
          title="Stop making clips?"
          description="The steps already done are kept, so you can start again later from where it stopped. Credits for the unfinished part come back to you."
          footer={
            <>
              <Button variant="secondary" data-autofocus onClick={() => setStopOpen(false)}>
                Keep going
              </Button>
              <Button variant="danger" onClick={() => setStopOpen(false)}>
                Stop
              </Button>
            </>
          }
        />
      </AppShell>
    </ScreenFrame>
  );
}

function StateBody({ state, onStop }: { state: string; onStop: () => void }) {
  if (state === 'waiting-credits') {
    return (
      <Card padding="lg" className="flex flex-col gap-3" role="alert">
        <div className="flex items-start gap-3">
          <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-cn-accent-text" />
          <div className="space-y-1">
            <h2 className="text-cn-title-sm font-semibold">Waiting for credits</h2>
            <p className="text-cn-body text-cn-fg-secondary">
              Your video is in. Making clips needs 116 credits and you have 6. I’ll start as soon as you add credits; nothing has been charged.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 pl-8">
          <Button>Add credits</Button>
          <Button variant="ghost">Change options</Button>
        </div>
      </Card>
    );
  }
  if (state === 'failed') {
    return (
      <ResultMessage
        status="failed"
        summary="Transcribing Episode 41 didn’t finish. The audio cut out at 31:08."
        safeNote="Your video is safe and the 116 credits are back in your balance."
        onRetry={() => undefined}
        timestamp="2 min ago"
      />
    );
  }
  if (state === 'stopped') {
    return (
      <ResultMessage
        status="stopped"
        summary="Stopped while finding the best moments."
        changes={['Audio cleaned', 'Transcript ready (8,412 words)']}
        safeNote="The steps done are kept. Starting again picks up from here."
        suggestions={['Start again', 'Only the first 30 minutes']}
        onSuggestion={() => undefined}
        timestamp="Just now"
      />
    );
  }
  if (state === 'done') {
    return (
      <ResultMessage
        status="done"
        summary="Done — 9 clips, reframed to 9:16 with Hinglish captions."
        changes={['23 moments scored; the top 9 kept', 'Titles and hashtags written for each clip']}
        suggestions={['Make 3 more', 'Shorter versions under 30 seconds']}
        onSuggestion={() => undefined}
        timestamp="Just now"
      />
    );
  }
  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      <Button variant="secondary" size="sm" onClick={onStop}>
        {state === 'uploading' ? 'Cancel upload' : 'Stop'}
      </Button>
    </div>
  );
}

function ReadyToast() {
  const toast = useToast();
  const shown = useRef(false);
  useEffect(() => {
    if (shown.current) return;
    shown.current = true;
    toast.show({ title: '9 clips ready', description: 'Episode 41 — Why we stopped chasing views', tone: 'success', action: { label: 'See clips', onClick: () => undefined } });
  }, [toast]);
  return null;
}
