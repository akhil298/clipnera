'use client';

import { ExternalLink, Plus, Search } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { Chip } from '@/components/ui/Chip';
import type { PromptContext } from '@/components/ui/ContextChip';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconButton } from '@/components/ui/IconButton';
import { PromptBar, type PromptMode } from '@/components/ui/PromptBar';
import { ResultMessage } from '@/components/ui/ResultMessage';
import { Skeleton, SkeletonGroup } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';
import { cx, focusWithinRing } from '@/lib/design/styles';

import { BrollPick } from '../_components/BrollPick';
import { MediaCard } from '../_components/MediaCard';
import { BROLL_ALTERNATES, CHIP_RANGE } from '../_components/sample';
import { ScreenShell, StateSwitcher } from '../_components/ScreenShell';

const STATES = [
  { value: 'browse', label: 'Browse' },
  { value: 'results', label: 'Search results' },
  { value: 'empty', label: 'No match' },
  { value: 'loading', label: 'Loading' },
  { value: 'error', label: 'Didn’t load' },
  { value: 'platform-only', label: 'Your uploads flag off' },
];

const SOURCES = [
  { title: 'kavya-interview.mov', length: '12:40', tone: 0, meta: 'Source · in this project' },
  { title: 'office-walkthrough.mp4', length: '1:12', tone: 3, meta: 'Added 2 Oct' },
];

export function AssetSidebar() {
  const toast = useToast();
  const [state, setState] = useState('browse');
  const [tab, setTab] = useState<'media' | 'clipnera' | 'uploads'>('clipnera');
  const [value, setValue] = useState('Add B-roll of coffee being poured over 0:12 – 0:16');
  const [mode, setMode] = useState<PromptMode>('edit');
  const [contexts, setContexts] = useState<PromptContext[]>([CHIP_RANGE]);
  const [picked, setPicked] = useState<string | null>(null);
  const uploads = state !== 'platform-only';

  const attachAsset = (title: string, length: string) => {
    setPicked(title);
    setContexts([...contexts.filter((context) => context.kind !== 'asset'), { id: `a-${title}`, kind: 'asset', label: title, meta: length }]);
    setValue('Use this clip over 0:12 – 0:16');
  };

  const grid = () => {
    if (state === 'loading')
      return (
        <SkeletonGroup label="Loading footage" className="grid grid-cols-2 gap-2">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="aspect-[9/16] w-full" />
          ))}
        </SkeletonGroup>
      );
    if (state === 'error')
      return (
        <EmptyState
          size="compact"
          level={3}
          title="The library didn’t load."
          description="Your project is safe."
          action={
            <Button size="sm" variant="secondary">
              Try again
            </Button>
          }
        />
      );
    if (state === 'empty')
      return (
        <EmptyState
          size="compact"
          level={3}
          title="No shots match “gold cappuccino art”"
          description="Try fewer words, or describe what’s on screen."
          action={
            <div className="flex flex-wrap justify-center gap-1.5">
              {['coffee pour', 'café counter', 'morning desk'].map((query) => (
                <Chip key={query} size="sm">
                  {query}
                </Chip>
              ))}
            </div>
          }
        />
      );
    const items = tab === 'media' ? SOURCES.map((item, index) => ({ ...item, id: `m${index}` })) : BROLL_ALTERNATES.map((shot) => ({ ...shot, meta: shot.source }));
    return (
      <>
        {state === 'results' && <p className="text-cn-caption text-cn-fg-muted">8 results · matches by meaning</p>}
        <ul className="grid grid-cols-2 gap-2">
          {items.map((item) => (
            <li key={item.id} className="relative">
              <MediaCard size="sm" title={item.title} length={item.length} tone={item.tone} meta={item.meta} selected={picked === item.title} actionLabel={`Select ${item.title}`} onOpen={() => attachAsset(item.title, item.length)} />
              <IconButton
                size="sm"
                variant="secondary"
                label={`Add ${item.title} at the playhead`}
                icon={<Plus />}
                onClick={() => toast.show({ title: `Added ${item.title} at 0:12`, description: 'One version: “Added B-roll at 0:12”.', action: { label: 'Undo', onClick: () => undefined } })}
                className="absolute right-1.5 top-1.5 z-cn-raised"
              />
            </li>
          ))}
        </ul>
      </>
    );
  };

  return (
    <ScreenShell
      title="Assets and B-roll"
      summary="The Editor’s entry into both libraries: Asset chip, /broll, and “chose this because” with one-click swap."
      flags={['new_ui_editor', 'broll_platform_library', 'broll_user_library']}
      controls={<StateSwitcher label="Library panel" options={STATES} value={state} onChange={setState} />}
    >
      <div className="grid gap-6 lg:grid-cols-[20rem_1fr]">
        <aside aria-label="Library panel" className="flex h-[44rem] flex-col gap-3 rounded-cn-xl border border-cn-border bg-cn-surface p-3">
          <div role="group" aria-label="Source" className="flex flex-wrap gap-1.5">
            <Chip size="sm" selected={tab === 'media'} onClick={() => setTab('media')}>
              This project
            </Chip>
            <Chip size="sm" selected={tab === 'clipnera'} onClick={() => setTab('clipnera')}>
              Clipnera library
            </Chip>
            {uploads && (
              <Chip size="sm" selected={tab === 'uploads'} onClick={() => setTab('uploads')}>
                Your uploads
              </Chip>
            )}
          </div>
          <label className={cx('flex h-9 items-center gap-2 rounded-cn-md border border-cn-control-border bg-cn-field px-2.5', focusWithinRing)}>
            <Search aria-hidden className="size-4 text-cn-fg-muted" />
            <span className="sr-only">Search footage</span>
            <input
              defaultValue={state === 'results' ? 'coffee pour' : state === 'empty' ? 'gold cappuccino art' : ''}
              placeholder="Search footage — try “drone shot of a city at night”"
              className="min-w-0 flex-1 bg-transparent text-cn-label text-cn-fg placeholder:text-cn-fg-muted focus-visible:outline-none"
            />
          </label>
          <div className="flex flex-wrap gap-1.5">
            <Chip size="sm" selected>
              Fits this project
            </Chip>
            <Chip size="sm">Under 5 s</Chip>
            <Chip size="sm">No people</Chip>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">{grid()}</div>
          <Button size="sm" variant="ghost" trailingIcon={<ExternalLink />} onClick={() => toast.show({ title: 'Opens /dashboard/library', description: 'Browse, upload, collections: the library screens.' })}>
            Open the full library
          </Button>
        </aside>

        <div className="flex flex-col gap-6">
          <Card padding="md">
            <CardHeader title="Select a tile → Asset chip; /broll fills a template" description="Selecting a tile attaches it to the prompt. /broll with a Range chip fills “over 0:12 – 0:16”; with an Asset chip, “Use this clip at…”. Nothing sends on its own." level={2} />
            <PromptBar
              className="mt-3"
              value={value}
              onValueChange={setValue}
              onSubmit={() => toast.show({ title: 'Sent', description: 'See the Editor mockup for the run.' })}
              mode={mode}
              onModeChange={setMode}
              contexts={contexts}
              onRemoveContext={(id) => setContexts(contexts.filter((context) => context.id !== id))}
              creditCost={2}
            />
          </Card>
          <Card padding="md">
            <CardHeader title="Result with the “why” line and Swap" description="Swap shows four alternates with hover preview; one click swaps as a new version." level={2} />
            <div className="mt-3 flex flex-col gap-3">
              <ResultMessage
                status="done"
                summary="Done — added B-roll at 0:12 – 0:16."
                version={{ name: 'Added B-roll at 0:12', onUndo: () => undefined, onCompare: () => undefined }}
                suggestions={['Add B-roll at 0:24 too']}
                onSuggestion={setValue}
              />
              <BrollPick
                pick={{ title: 'Pouring coffee into a white mug', source: 'your uploads', range: '0:12 – 0:16', reasons: ['matches “coffee” and “pour”', 'is from your library', 'fits 9:16'] }}
                onOpenLibrary={() => setState('results')}
              />
            </div>
          </Card>
        </div>
      </div>
    </ScreenShell>
  );
}
