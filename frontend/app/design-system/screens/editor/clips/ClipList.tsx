'use client';

import { ArrowLeft, CalendarClock, Copy, Download, Pencil, Play, Plus, RotateCcw, Scissors } from 'lucide-react';
import { useState } from 'react';

import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, cardLinkOverlay } from '@/components/ui/Card';
import { Checkbox } from '@/components/ui/Checkbox';
import { Chip } from '@/components/ui/Chip';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconButton } from '@/components/ui/IconButton';
import { Menu } from '@/components/ui/Menu';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { PromptBar, type PromptMode } from '@/components/ui/PromptBar';
import { ScoreRing } from '@/components/ui/ScoreRing';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Skeleton, SkeletonGroup } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';
import { WorkingText } from '@/components/ui/WorkingText';
import { cx } from '@/lib/design/styles';

import { Poster, PreviewSweep, useHoverPreview } from '../_components/MediaCard';
import { type ClipRow, CLIPS, PROJECT } from '../_components/sample';
import { ScreenShell, StateSwitcher } from '../_components/ScreenShell';

const STATES = [
  { value: 'ready', label: 'Clips ready' },
  { value: 'processing', label: 'Still finding clips' },
  { value: 'failed', label: 'Stopped' },
  { value: 'filter-empty', label: 'Filter shows none' },
  { value: 'loading', label: 'Loading' },
];

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-2 text-cn-caption">
      <span className="w-14 text-cn-fg-muted">{label}</span>
      <span className="h-1 flex-1 overflow-hidden rounded-cn-full bg-cn-surface-active">
        <span className="block h-full rounded-cn-full bg-cn-fg-secondary" style={{ width: `${value}%` }} />
      </span>
      <span className="w-6 text-right font-cn-mono tabular-nums text-cn-fg-secondary">{value}</span>
    </div>
  );
}

/**
 * Successor of ClipCard: hover-to-preview kept (150 ms, muted, one audible
 * card at a time), now keyboard reachable — the title is the one link and
 * covers the card; other controls sit above it.
 */
function ClipTile({ clip, rank, selectMode, checked, onCheck }: { clip: ClipRow; rank: number; selectMode: boolean; checked: boolean; onCheck: () => void }) {
  const toast = useToast();
  const { playing, handlers } = useHoverPreview();
  return (
    <Card padding="none" interactive selected={checked} className="relative flex flex-col overflow-hidden" {...handlers}>
      <Poster tone={clip.tone}>
        <span className="absolute left-2 top-2 z-cn-raised">
          {selectMode ? (
            <Checkbox label={<span className="sr-only">Select {clip.title}</span>} checked={checked} onChange={onCheck} />
          ) : (
            <span className="rounded-cn-xs bg-cn-bg/80 px-1.5 font-cn-mono text-cn-caption tabular-nums text-cn-fg">#{rank}</span>
          )}
        </span>
        <ScoreRing score={clip.score} className="absolute right-2 top-2 size-9" />
        <IconButton
          label={`Play ${clip.title} with sound`}
          icon={<Play />}
          variant="secondary"
          className="absolute left-1/2 top-1/2 z-cn-raised -translate-x-1/2 -translate-y-1/2 rounded-cn-full opacity-0 focus-visible:opacity-100 group-hover:opacity-100 [@media(hover:none)]:opacity-100"
        />
        <span className="absolute bottom-2 left-2 rounded-cn-xs bg-cn-bg/80 px-1 font-cn-mono text-cn-caption tabular-nums">{clip.range}</span>
        <span className="absolute bottom-2 right-2 rounded-cn-xs bg-cn-bg/80 px-1 font-cn-mono text-cn-caption tabular-nums">{clip.length}</span>
        <PreviewSweep playing={playing} />
      </Poster>
      <div className="flex flex-1 flex-col gap-2 p-3">
        <a href="#editor" className={cx('line-clamp-2 text-cn-label font-semibold text-cn-fg', cardLinkOverlay)}>
          {clip.title}
        </a>
        <div className="relative z-cn-raised flex items-start gap-1.5 rounded-cn-md bg-cn-surface-hover p-2">
          <p className="line-clamp-2 flex-1 text-cn-caption italic text-cn-fg-secondary">{clip.hook}</p>
          <IconButton size="sm" className="size-6" label="Copy hook" icon={<Copy />} onClick={() => toast.show({ title: 'Hook copied', tone: 'success' })} />
        </div>
        <ScoreBar label="Hook" value={clip.hookScore} />
        <ScoreBar label="Engage" value={clip.engage} />
        <div className="relative z-cn-raised mt-auto flex items-center gap-1 pt-1">
          <Button size="sm" variant="secondary" leadingIcon={<Scissors />} className="flex-1">
            Edit
          </Button>
          <IconButton size="sm" label="Schedule post" icon={<CalendarClock />} />
          <IconButton size="sm" label="Download clip" icon={<Download />} onClick={() => toast.show({ title: `Exporting ${clip.title}`, description: 'Runs in the background. You’ll get a notification.' })} />
        </div>
      </div>
    </Card>
  );
}

export function ClipList() {
  const toast = useToast();
  const [state, setState] = useState('ready');
  const [selectMode, setSelectMode] = useState(false);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [prompt, setPrompt] = useState('');
  const [mode, setMode] = useState<PromptMode>('edit');
  const [sort, setSort] = useState('score');
  const processing = state === 'processing';
  const clips = processing ? CLIPS.slice(0, 3) : state === 'filter-empty' ? [] : CLIPS;

  const toggle = (id: string) => {
    const next = new Set(checked);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setChecked(next);
  };

  return (
    <ScreenShell title="Project clips" summary="Successor of ClipGeneratorView: live step, source map, clip grid with hover preview." flags={['new_ui_dashboard', 'new_ui_editor']} controls={<StateSwitcher label="State" options={STATES} value={state} onChange={setState} />}>
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <header className="flex flex-col gap-3">
          <a href="#projects" className="inline-flex items-center gap-1 self-start text-cn-label font-semibold text-cn-fg-secondary hover:text-cn-fg">
            <ArrowLeft aria-hidden className="size-4" /> Projects
          </a>
          <div className="flex flex-wrap items-center gap-2">
            {processing ? <StatusBadge status="processing">Finding moments</StatusBadge> : state === 'failed' ? <StatusBadge status="failed">Stopped</StatusBadge> : <StatusBadge status="ready">{CLIPS.length} clips ready</StatusBadge>}
            <Badge>Interview</Badge>
            <Badge>24 credits used</Badge>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <h1 className="flex items-center gap-2 text-cn-title-lg font-bold">
              {PROJECT.title}
              <IconButton size="sm" label="Rename project" icon={<Pencil />} />
            </h1>
            <span className="flex-1" />
            <Button variant="secondary" leadingIcon={<Plus />}>
              Add more
            </Button>
            <Button variant="secondary" leadingIcon={<Download />} disabled={clips.length === 0} onClick={() => toast.show({ title: `Exporting ${clips.length} clips`, description: 'Each with its own saved settings. You can leave this page.' })}>
              Export all {clips.length}
            </Button>
          </div>
          <p className="text-cn-label text-cn-fg-secondary">
            Original source · {PROJECT.sourceLength} · average score <span className="font-semibold text-cn-fg">87</span> · <a href="#source" className="underline">Original video</a> · <button type="button" className="underline" onClick={() => toast.show({ title: 'Project ID copied' })}>Copy ID</button>
          </p>
        </header>

        <PromptBar
          value={prompt}
          onValueChange={setPrompt}
          onSubmit={() => toast.show({ title: 'Sent', description: 'Runs across all clips in this project.' })}
          mode={mode}
          onModeChange={setMode}
          placeholder="Find more clips, or change all of them — “find 3 more about pricing”"
          creditCost={prompt ? 6 : undefined}
        />

        {processing && (
          <Card padding="md" className="flex flex-col gap-2">
            <p className="text-cn-body">
              <WorkingText>Finding the best moments · 7 of 12:40 watched</WorkingText>
            </p>
            <ProgressBar label="Finding the best moments" value={55} valueText="Step 3 of 4" />
            <p className="text-cn-caption text-cn-fg-muted">Clips appear here as soon as each is ready. This runs on our servers; you can close the tab.</p>
          </Card>
        )}
        {state === 'failed' && (
          <Card padding="md" className="flex flex-wrap items-center gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-cn-body font-semibold text-cn-danger-text">Finding clips stopped at “Transcribing”.</p>
              <p className="text-cn-label text-cn-fg-secondary">Your video is safe and nothing was charged for the unfinished part.</p>
            </div>
            <Button leadingIcon={<RotateCcw />}>Try again</Button>
          </Card>
        )}

        <Card padding="md">
          <div className="mb-2 flex items-center gap-2">
            <h2 className="text-cn-label font-semibold">Where the clips come from</h2>
            <span className="text-cn-caption text-cn-fg-muted">each block is a clip, numbered by rank</span>
            <span className="flex-1" />
            <span className="font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">0:00 – {PROJECT.sourceLength}</span>
          </div>
          <div className="relative h-11 rounded-cn-md bg-cn-surface-hover">
            {clips.map((clip, index) => (
              <button
                key={clip.id}
                type="button"
                aria-label={`Clip ${index + 1}: ${clip.title}, ${clip.range}`}
                className="absolute inset-y-1.5 flex items-center justify-center rounded-cn-xs border border-cn-border-strong bg-cn-surface-active font-cn-mono text-cn-caption hover:border-cn-accent-border"
                style={{ left: `${8 + index * 14}%`, width: '5%' }}
              >
                {index + 1}
              </button>
            ))}
          </div>
        </Card>

        <section aria-labelledby="clips-heading" className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <h2 id="clips-heading" className="text-cn-title-sm font-semibold">
              Clips <Badge>{clips.length}</Badge>
            </h2>
            <span className="flex-1" />
            <Chip size="sm" selected={selectMode} onClick={() => setSelectMode(!selectMode)}>
              {selectMode ? 'Done' : 'Select'}
            </Chip>
            <SegmentedControl label="Sort" size="sm" value={sort} onValueChange={setSort} options={[{ value: 'score', label: 'Highest score' }, { value: 'order', label: 'Video order' }, { value: 'length', label: 'Longest' }]} />
            <Menu
              trigger={(props) => (
                <Button {...props} size="sm" variant="secondary">
                  All scores
                </Button>
              )}
              items={[
                { id: 'all', label: 'All scores', checked: true, onSelect: () => undefined },
                { id: '70', label: 'Standard (70+)', onSelect: () => undefined },
                { id: '85', label: 'High (85+)', onSelect: () => undefined },
                { id: '90', label: 'Top (90+)', onSelect: () => setState('filter-empty') },
              ]}
            />
          </div>
          {selectMode && (
            <div className="sticky top-0 z-cn-sticky flex flex-wrap items-center gap-2 rounded-cn-lg border border-cn-border-strong bg-cn-surface-raised px-3 py-2 shadow-cn-2">
              <span className="text-cn-label font-semibold">{checked.size ? `${checked.size} selected` : 'Select clips to export together'}</span>
              <span className="flex-1" />
              <Button size="sm" variant="ghost" onClick={() => setChecked(new Set(CLIPS.map((clip) => clip.id)))}>
                Select all
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setChecked(new Set())}>
                Clear
              </Button>
              <Button size="sm" disabled={checked.size === 0}>
                Export {checked.size}
              </Button>
            </div>
          )}
          {state === 'loading' ? (
            <SkeletonGroup label="Loading clips" className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 4 }, (_, index) => (
                <Skeleton key={index} className="aspect-[9/16] w-full" />
              ))}
            </SkeletonGroup>
          ) : state === 'filter-empty' ? (
            <EmptyState size="compact" title="No clips match this score filter." action={<Button variant="secondary" onClick={() => setState('ready')}>Show all scores</Button>} />
          ) : (
            <ul className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-4">
              {clips.map((clip, index) => (
                <li key={clip.id}>
                  <ClipTile clip={clip} rank={index + 1} selectMode={selectMode} checked={checked.has(clip.id)} onCheck={() => toggle(clip.id)} />
                </li>
              ))}
              {processing &&
                Array.from({ length: 2 }, (_, index) => (
                  <li key={`pending-${index}`}>
                    <Poster tone={index + 3} className="rounded-cn-lg border border-cn-border">
                      <span className="absolute inset-x-0 bottom-3 text-center text-cn-caption">
                        <WorkingText>Cutting clip {4 + index}</WorkingText>
                      </span>
                    </Poster>
                  </li>
                ))}
            </ul>
          )}
        </section>
      </div>
    </ScreenShell>
  );
}
