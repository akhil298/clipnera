'use client';

import { Sparkles } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { ContextChip, type PromptContext } from '@/components/ui/ContextChip';

import { PreviewPlayer } from '../_components/PreviewPlayer';
import { CAPTION_IDS, CHIP_CLIP, type TimelineBlock } from '../_components/sample';
import { ScreenShell, StateSwitcher } from '../_components/ScreenShell';
import { Timeline } from '../_components/Timeline';

const STATES = [
  { value: 'before', label: 'Before trim (silences hatched)' },
  { value: 'landed', label: 'An operation lands' },
  { value: 'locked', label: 'Locked while a step works' },
  { value: 'captions', label: 'Captions added' },
  { value: 'broll', label: 'B-roll lane' },
  { value: 'phone', label: 'Phone strip' },
];

const PREVIEW = [
  { value: 'preview', label: 'Preview quality' },
  { value: 'full', label: 'Full quality' },
  { value: 'jump', label: 'Jump to change' },
  { value: 'loading', label: 'Loading' },
  { value: 'error', label: 'Can’t play' },
];

const REVISION: Record<string, number> = { before: 40, landed: 41, locked: 41, captions: 42, broll: 43, phone: 43 };

export function TimelineStates() {
  const [state, setState] = useState('landed');
  const [preview, setPreview] = useState('preview');
  const [key, setKey] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [chip, setChip] = useState<PromptContext>(CHIP_CLIP);
  const [time, setTime] = useState(3);
  const revision = REVISION[state];
  const highlightIds = state === 'captions' ? CAPTION_IDS : state === 'broll' ? ['b1'] : ['v1', 'v2', 'v3'];

  const onSelect = (block: TimelineBlock | null) => {
    setSelected(block?.id ?? null);
    setChip(block ? { id: block.id, kind: block.lane === 'captions' ? 'caption' : 'clip', label: block.lane === 'captions' ? `“${block.label}”` : block.label } : CHIP_CLIP);
  };

  const controls = (
    <>
      <StateSwitcher label="Timeline" options={STATES} value={state} onChange={setState} />
      <Button size="sm" variant="secondary" leadingIcon={<Sparkles />} onClick={() => setKey(key + 1)}>
        Replay the 600 ms highlight
      </Button>
      <StateSwitcher label="Preview" options={PREVIEW} value={preview} onChange={setPreview} />
    </>
  );

  return (
    <ScreenShell title="Timeline and preview" summary="Tracks, the landing highlight, locks, selection as a chip, proxy quality." flags={['new_ui_editor_timeline']} controls={controls}>
      <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
        <div className="flex flex-col gap-4">
          <div className="overflow-hidden rounded-cn-xl border border-cn-border">
            <Timeline
              revision={revision}
              locked={state === 'locked' ? ['v2', 'v3'] : []}
              highlight={state === 'before' || state === 'locked' ? null : { ids: highlightIds, key }}
              selectedId={selected}
              onSelect={onSelect}
              playhead={time}
              onSeek={setTime}
              compact={state === 'phone'}
              className={state === 'phone' ? 'mx-auto h-28 w-[390px] max-w-full' : 'h-72'}
            />
          </div>
          <Card padding="md">
            <CardHeader title="Point, then prompt" description="Select a block above (click, or Tab into the grid and press Enter). It becomes the prompt’s chip." level={2} />
            <div className="mt-3">
              <ContextChip context={chip} />
            </div>
          </Card>
          {state === 'locked' && (
            <p className="text-cn-label text-cn-fg-secondary">Try selecting “The price” or pressing Delete on it: the 423 response becomes a toast. Locks clear on run.lock.released.</p>
          )}
        </div>
        <div className="h-[36rem] overflow-hidden rounded-cn-xl border border-cn-border">
          <PreviewPlayer
            time={preview === 'jump' ? 26 : time}
            length={30}
            playing={false}
            onPlayPause={() => undefined}
            onSeek={setTime}
            quality={preview === 'full' ? 'full' : 'preview'}
            captions={revision >= 42}
            title={time < 5 ? 'Why ₹499 works' : null}
            broll={state === 'broll' && time >= 12 && time < 16}
            changedRange={preview === 'jump' ? [12, 16] : null}
            status={preview === 'loading' ? 'loading' : preview === 'error' ? 'error' : 'ready'}
            className="h-full"
          />
        </div>
      </div>
    </ScreenShell>
  );
}
