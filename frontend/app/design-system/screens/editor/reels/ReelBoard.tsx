'use client';

import { Clapperboard, Copy, Film, Images, Plus, Wand2 } from 'lucide-react';
import { useState } from 'react';

import {
  Badge,
  Button,
  Card,
  Chip,
  Disclosure,
  EmptyState,
  FileDropzone,
  Input,
  MediaCard,
  ProgressSteps,
  PromptBar,
  SegmentedControl,
  StatusBadge,
  Switch,
  WorkingText,
  type Status,
} from '@/components/ui';

import { ScreenShell, StateSwitcher } from '../_components/ScreenShell';

const VIEWS = [
  { value: 'list', label: 'Reels list' },
  { value: 'empty', label: 'No reels' },
  { value: 'images', label: 'Image reel board' },
  { value: 'analysing', label: 'Footage: analysing' },
  { value: 'planned', label: 'Footage: plan ready' },
  { value: 'done', label: 'Footage: done' },
];

const REELS: ReadonlyArray<{ id: string; title: string; status: Status; label: string; kind: 'Footage' | 'Images'; duration: number; time: string }> = [
  { id: 'r1', title: 'Morning routine', status: 'ready', label: 'Done', kind: 'Footage', duration: 32, time: '2 h ago' },
  { id: 'r2', title: 'Chai stall story', status: 'processing', label: 'Rendering', kind: 'Footage', duration: 45, time: '10 min ago' },
  { id: 'r3', title: 'Five pricing myths', status: 'draft', label: 'Plan ready', kind: 'Images', duration: 28, time: 'Yesterday' },
  { id: 'r4', title: 'Studio tour', status: 'failed', label: 'Failed', kind: 'Footage', duration: 60, time: '3 Oct' },
];

const SCENES = ['Hook: “Nobody tells you this”', 'Myth 1: cheaper sells more', 'Myth 2: discounts build trust', 'The fix', 'Call to action'];

const ANALYSE_STEPS = [
  { id: 'upload', label: 'Footage received', status: 'done' as const },
  { id: 'watch', label: 'Watching every shot', status: 'done' as const },
  { id: 'listen', label: 'Listening to the audio', status: 'active' as const },
  { id: 'match', label: 'Matching the script', status: 'upcoming' as const },
  { id: 'plan', label: 'Writing the plan', status: 'upcoming' as const },
];

/** Reels (editor §14): list and create, the image reel board and the footage reel board. */
export function ReelBoard() {
  const [view, setView] = useState('list');
  return (
    <ScreenShell
      title="Reels"
      summary="Create from footage or images, the reels grid, the image scene board and the footage board from analysing to done."
      flags={['new_ui_reels', 'broll_studio.reels', 'broll_studio.reels.footage']}
      controls={<StateSwitcher label="View" options={VIEWS} value={view} onChange={setView} />}
    >
      {view === 'list' || view === 'empty' ? <ReelsList empty={view === 'empty'} /> : view === 'images' ? <ImageBoard /> : <FootageBoard stage={view as 'analysing' | 'planned' | 'done'} />}
    </ScreenShell>
  );
}

function ReelsList({ empty }: { empty: boolean }) {
  const [kind, setKind] = useState('footage');
  return (
    <div className="mx-auto grid w-full max-w-7xl gap-6 lg:grid-cols-[theme(spacing.96)_1fr]">
      <Card padding="md" className="flex flex-col gap-4 self-start">
        <h2 className="text-cn-title-sm font-semibold">New reel</h2>
        <SegmentedControl label="Start from" value={kind} onValueChange={setKind} options={[{ value: 'footage', label: 'Edit my footage' }, { value: 'images', label: 'Build from images' }]} />
        <Input label="Title" hint="Optional" placeholder="Morning routine" />
        {kind === 'footage' ? (
          <>
            <FileDropzone title="Drop your raw videos and photos" hint="MP4, MOV, JPG, PNG · up to 5 min of footage on your plan" accept="video/*,image/*" multiple onFiles={() => undefined} />
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Length">
              {['Auto', '15 s', '30 s', '45 s', '60 s'].map((length, index) => (
                <Chip key={length} size="sm" selected={index === 0}>
                  {length}
                </Chip>
              ))}
            </div>
            <Disclosure title="Add a script">
              <p className="text-cn-label text-cn-fg-secondary">Paste the lines you want said, then choose how Clipnera uses them.</p>
            </Disclosure>
            <Switch label="Autopilot" description="Render as soon as the plan is ready" />
            <Button leadingIcon={<Wand2 />}>Analyse footage</Button>
            <p className="text-cn-caption text-cn-fg-muted">Planning and previews are free. Rendering uses credits; the cost shows first.</p>
          </>
        ) : (
          <>
            <SegmentedControl label="Script" size="sm" defaultValue="auto" options={[{ value: 'auto', label: 'Write it for me' }, { value: 'own', label: 'My own script' }]} />
            <FileDropzone title="Add 2 to 5 images" accept="image/*" multiple onFiles={() => undefined} compact />
            <Button leadingIcon={<Images />}>Build scene board</Button>
          </>
        )}
      </Card>
      {empty ? (
        <EmptyState icon={<Clapperboard />} title="No reels yet" description="Your reels show up here with their cover and status." />
      ) : (
        <ul aria-label="Reels" className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4">
          {REELS.map((reel) => (
            <li key={reel.id}>
              <MediaCard
                title={reel.title}
                meta={`${reel.kind} · ${reel.time}`}
                duration={reel.duration}
                topLeft={<StatusBadge status={reel.status}>{reel.label}</StatusBadge>}
                bottomLeft={<Badge icon={reel.kind === 'Footage' ? <Film /> : <Images />}>{reel.kind}</Badge>}
                actionLabel={`Open ${reel.title}`}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ImageBoard() {
  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
      <header className="flex flex-wrap items-center gap-3">
        <h2 className="text-cn-title-lg font-semibold">Five pricing myths</h2>
        <StatusBadge status="draft">Plan ready</StatusBadge>
        <span className="flex-1" />
        <Button>Render · 40 credits</Button>
      </header>
      <ol aria-label="Scenes" className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {SCENES.map((scene, index) => (
          <li key={scene} className="flex flex-col gap-2 rounded-cn-lg border border-cn-border bg-cn-surface p-2">
            <div className="cn-media-edge aspect-cn-portrait rounded-cn-md bg-cn-stage" />
            <p className="flex items-center justify-between text-cn-caption text-cn-fg-muted">
              <span>Scene {index + 1}</span>
              <span className="font-cn-mono tabular-nums">
                {(index * 3.4).toFixed(1)}–{((index + 1) * 3.4).toFixed(1)}s
              </span>
            </p>
            <p className="line-clamp-2 text-cn-label text-cn-fg">{scene}</p>
            <SegmentedControl label={`Scene ${index + 1} shows`} size="sm" defaultValue="image" options={[{ value: 'image', label: 'Image' }, { value: 'broll', label: 'B-roll' }, { value: 'text', label: 'Text' }]} />
          </li>
        ))}
      </ol>
    </div>
  );
}

function FootageBoard({ stage }: { stage: 'analysing' | 'planned' | 'done' }) {
  const [prompt, setPrompt] = useState('');
  return (
    <div className="mx-auto grid w-full max-w-5xl gap-6 md:grid-cols-[theme(spacing.72)_1fr]">
      <div className="cn-media-edge aspect-cn-portrait w-full max-w-xs self-start rounded-cn-lg bg-cn-stage" aria-label="Reel preview" role="img" />
      <div className="flex flex-col gap-4">
        <header className="flex flex-wrap items-center gap-2">
          <h2 className="text-cn-title font-semibold">Morning routine</h2>
          <StatusBadge status={stage === 'done' ? 'ready' : stage === 'analysing' ? 'processing' : 'draft'}>
            {stage === 'done' ? 'Done' : stage === 'analysing' ? 'Analysing' : 'Plan ready'}
          </StatusBadge>
        </header>
        {stage === 'analysing' && (
          <>
            <ProgressSteps label="Analysing your footage" steps={ANALYSE_STEPS} orientation="vertical" />
            <p className="text-cn-label text-cn-fg-secondary">
              <WorkingText>Listening to the audio</WorkingText>. You can leave this page; I’ll tell you when the plan is ready.
            </p>
          </>
        )}
        {stage === 'planned' && (
          <>
            <Card padding="md" className="flex flex-col gap-3">
              <h3 className="text-cn-label font-semibold">The plan</h3>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-cn-label">
                <dt className="text-cn-fg-muted">Type</dt>
                <dd>Day-in-the-life</dd>
                <dt className="text-cn-fg-muted">Length</dt>
                <dd className="font-cn-mono tabular-nums">0:32</dd>
                <dt className="text-cn-fg-muted">Music</dt>
                <dd>Calm piano · licensed</dd>
              </dl>
              <Input label="Hook" defaultValue="This is how my day really starts" />
            </Card>
            <PromptBar value={prompt} onValueChange={setPrompt} onSubmit={() => setPrompt('')} modes={[]} hint="5 changes left" label="Change the plan" placeholder="Make the hook shorter" />
            <div className="flex flex-wrap gap-2">
              <Button leadingIcon={<Plus />}>Render · 24 credits</Button>
              <Button variant="secondary">Open in editor</Button>
              <Button variant="ghost">Try a different plan · 2 left</Button>
            </div>
          </>
        )}
        {stage === 'done' && (
          <>
            <Card padding="md" className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-cn-label font-semibold">Music credit</h3>
                <p className="text-cn-label text-cn-fg-secondary">“Calm piano” by a public-domain artist</p>
              </div>
              <Button size="sm" variant="ghost" leadingIcon={<Copy />}>
                Copy
              </Button>
            </Card>
            <div className="flex flex-wrap gap-2">
              <Button>Download</Button>
              <Button variant="secondary">Render again</Button>
            </div>
            <p className="text-cn-caption text-cn-fg-muted">Re-renders cost a quarter of the first render.</p>
          </>
        )}
      </div>
    </div>
  );
}
