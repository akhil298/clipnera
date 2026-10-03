'use client';

import { Lock, Minus, Plus, Volume2, VolumeX } from 'lucide-react';
import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';

import { IconButton } from '@/components/ui/IconButton';
import { Kbd } from '@/components/ui/Kbd';
import { useToast } from '@/components/ui/Toast';
import { cx } from '@/lib/design/styles';
import { duration } from '@/lib/design/tokens';

import { clock, LANES, type LaneKind, REVISIONS, type TimelineBlock, VIEW_SECONDS } from './sample';

/** Lane colours by kind, all on palette (02 §5.2). No fuchsia title lane. */
const LANE_STYLE: Record<LaneKind, string> = {
  title: 'bg-cn-accent-subtle text-cn-accent-text',
  video: 'bg-cn-surface-active text-cn-fg',
  captions: 'bg-cn-accent-subtle text-cn-accent-text',
  broll: 'bg-cn-success-subtle text-cn-success-text',
  music: 'bg-cn-info-subtle text-cn-info-text',
  speech: 'bg-cn-info-subtle text-cn-info-text',
};

export const ITEM_LOCKED_COPY = 'Clipnera is editing this clip. It’s yours again when the step ends.';

export function blocksAt(revision: number): ReadonlyArray<TimelineBlock> {
  const known = Object.keys(REVISIONS)
    .map(Number)
    .filter((rev) => rev <= revision)
    .sort((a, b) => b - a)[0];
  return REVISIONS[known ?? 40];
}

/** Lit for 600 ms after an operation lands; a static outline under reduced motion. */
function useLit(highlight: { ids: string[]; key: number } | null): Set<string> {
  const [lit, setLit] = useState<Set<string>>(new Set());
  useEffect(() => {
    if (!highlight) return;
    setLit(new Set(highlight.ids));
    const id = setTimeout(() => setLit(new Set()), duration.highlight);
    return () => clearTimeout(id);
  }, [highlight]);
  return lit;
}

export interface TimelineProps {
  revision: number;
  locked?: ReadonlyArray<string>;
  highlight?: { ids: string[]; key: number } | null;
  selectedId?: string | null;
  onSelect?: (block: TimelineBlock | null) => void;
  playhead: number;
  onSeek?: (seconds: number) => void;
  /** Phone strip: video and captions only, no header column. */
  compact?: boolean;
  className?: string;
}

/**
 * Design-system addition (02 §5.2): tracks, clip blocks, the 600 ms amber
 * landing highlight and locked items. The timeline is a `grid`: one tab stop,
 * arrows move between blocks and lanes, Enter selects, Delete removes,
 * [ and ] trim to the playhead while the timeline has focus.
 */
export function Timeline({ revision, locked = [], highlight = null, selectedId = null, onSelect, playhead, onSeek, compact = false, className }: TimelineProps) {
  const toast = useToast();
  const [zoom, setZoom] = useState(1);
  const [muted, setMuted] = useState<Record<string, boolean>>({});
  const blocks = blocksAt(revision);
  const lit = useLit(highlight);
  const lanes = compact ? LANES.filter((lane) => lane.id === 'video' || lane.id === 'captions' || lane.id === 'broll') : LANES;
  const byLane = useMemo(
    () => Object.fromEntries(lanes.map((lane) => [lane.id, blocks.filter((block) => block.lane === lane.id && !(compact && block.cut))])) as Record<LaneKind, TimelineBlock[]>,
    [blocks, lanes, compact],
  );
  const [focusId, setFocusId] = useState<string>('v1');
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const pct = (seconds: number) => `${(seconds / VIEW_SECONDS) * 100}%`;
  const length = Math.max(...blocks.filter((block) => block.lane === 'video' && !block.cut).map((block) => block.end));

  const isLocked = (id: string) => locked.includes(id);

  const refuseLocked = () => toast.show({ title: 'This clip is locked for a moment', description: ITEM_LOCKED_COPY });

  const select = (block: TimelineBlock) => {
    if (isLocked(block.id)) return refuseLocked();
    onSelect?.(selectedId === block.id ? null : block);
  };

  const moveFocus = (id: string) => {
    setFocusId(id);
    refs.current[id]?.focus();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const current = blocks.find((block) => block.id === focusId);
    if (!current) return;
    const laneIndex = lanes.findIndex((lane) => lane.id === current.lane);
    const row = byLane[current.lane] ?? [];
    const index = row.findIndex((block) => block.id === current.id);
    const nearest = (laneId: LaneKind) =>
      (byLane[laneId] ?? []).reduce<TimelineBlock | null>(
        (best, block) => (!best || Math.abs(block.start - current.start) < Math.abs(best.start - current.start) ? block : best),
        null,
      );
    const go = (block: TimelineBlock | null | undefined) => {
      if (!block) return;
      event.preventDefault();
      moveFocus(block.id);
    };
    switch (event.key) {
      case 'ArrowRight':
        return go(row[index + 1]);
      case 'ArrowLeft':
        return go(row[index - 1]);
      case 'ArrowDown':
        for (let next = laneIndex + 1; next < lanes.length; next += 1) if (byLane[lanes[next].id]?.length) return go(nearest(lanes[next].id));
        return;
      case 'ArrowUp':
        for (let next = laneIndex - 1; next >= 0; next -= 1) if (byLane[lanes[next].id]?.length) return go(nearest(lanes[next].id));
        return;
      case 'Delete':
      case 'Backspace':
        event.preventDefault();
        if (isLocked(current.id)) return refuseLocked();
        return toast.show({ title: `Removed ${current.label}`, description: 'Saved with your other hand edits.', action: { label: 'Undo', onClick: () => undefined } });
      case '[':
      case ']':
        event.preventDefault();
        if (isLocked(current.id)) return refuseLocked();
        return toast.show({ title: `Trimmed the ${event.key === '[' ? 'start' : 'end'} of ${current.label} to ${clock(playhead)}` });
      default:
    }
  };

  return (
    <section aria-label="Timeline" className={cx('flex min-h-0 flex-col bg-cn-surface', className)}>
      {!compact && (
        <div className="flex h-9 shrink-0 items-center gap-2 border-b border-cn-border px-3">
          <span className="font-cn-mono text-cn-caption tabular-nums text-cn-fg-secondary">
            {clock(playhead)} / {clock(length)}
          </span>
          <span className="hidden text-cn-caption text-cn-fg-muted md:inline">
            Select a block to point the prompt at it · <Kbd keys={['[']} /> <Kbd keys={[']']} /> trim to playhead
          </span>
          <span className="flex-1" />
          <IconButton size="sm" label="Zoom out" icon={<Minus />} disabled={zoom <= 1} onClick={() => setZoom(Math.max(1, zoom - 0.5))} />
          <span className="w-9 text-center font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">{zoom}×</span>
          <IconButton size="sm" label="Zoom in" icon={<Plus />} disabled={zoom >= 4} onClick={() => setZoom(Math.min(4, zoom + 0.5))} />
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-auto">
        <div className="flex" style={{ minWidth: `${zoom * 100}%` }}>
          {!compact && (
            <div className="sticky left-0 z-cn-raised w-24 shrink-0 border-r border-cn-border bg-cn-surface">
              <div className="h-6 border-b border-cn-border" />
              {lanes.map((lane) => (
                <div key={lane.id} className={cx('flex items-center gap-1 border-b border-cn-border px-2 text-cn-caption text-cn-fg-secondary', lane.id === 'video' ? 'h-12' : 'h-8')}>
                  <span className="flex-1 truncate">{lane.label}</span>
                  {(lane.id === 'music' || lane.id === 'speech') && (
                    <IconButton
                      size="sm"
                      className="size-6"
                      label={`${muted[lane.id] ? 'Unmute' : 'Mute'} ${lane.label.toLowerCase()}`}
                      pressed={muted[lane.id]}
                      icon={muted[lane.id] ? <VolumeX /> : <Volume2 />}
                      onClick={() => setMuted({ ...muted, [lane.id]: !muted[lane.id] })}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
          <div className="relative min-w-0 flex-1">
            {/* Ruler: click to move the playhead. */}
            <div
              aria-hidden
              onPointerDown={(event) => {
                const rect = event.currentTarget.getBoundingClientRect();
                onSeek?.(((event.clientX - rect.left) / rect.width) * VIEW_SECONDS);
              }}
              className="relative h-6 cursor-pointer border-b border-cn-border"
            >
              {Array.from({ length: VIEW_SECONDS / 5 + 1 }, (_, index) => (
                <span key={index} className="absolute top-0 h-full border-l border-cn-border pl-1 font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted" style={{ left: pct(index * 5) }}>
                  {index % 2 === 0 ? clock(index * 5) : ''}
                </span>
              ))}
            </div>
            <div role="grid" aria-label="Tracks" aria-rowcount={lanes.length} onKeyDown={onKeyDown}>
              {lanes.map((lane) => (
                <div key={lane.id} role="row" aria-label={lane.label} className={cx('relative border-b border-cn-border', lane.id === 'video' ? 'h-12' : 'h-8')}>
                  {lane.id === 'speech' && (
                    <span aria-hidden className="absolute inset-y-1 left-0 flex items-center gap-px" style={{ width: pct(length) }}>
                      {Array.from({ length: 90 }, (_, index) => (
                        <span key={index} className="flex-1 rounded-cn-full bg-cn-info/60" style={{ height: `${25 + ((index * 37) % 70)}%` }} />
                      ))}
                    </span>
                  )}
                  {lane.id !== 'speech' &&
                    (byLane[lane.id] ?? []).map((block) => {
                      const lockedNow = isLocked(block.id);
                      const selected = selectedId === block.id;
                      return (
                        <button
                          key={block.id}
                          ref={(node) => {
                            refs.current[block.id] = node;
                          }}
                          type="button"
                          role="gridcell"
                          tabIndex={focusId === block.id ? 0 : -1}
                          aria-selected={selected}
                          aria-disabled={lockedNow || undefined}
                          aria-label={`${lane.label}: ${block.label}, ${clock(block.start)} to ${clock(block.end)}${lockedNow ? ', locked while Clipnera works on it' : ''}${block.cut ? ', cut' : ''}`}
                          onFocus={() => setFocusId(block.id)}
                          onClick={() => select(block)}
                          className={cx(
                            'absolute inset-y-1 flex items-center gap-1 overflow-hidden rounded-cn-sm px-1.5 text-left text-cn-caption',
                            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-cn-focus',
                            block.cut ? 'border border-dashed border-cn-danger/60 bg-cn-danger-subtle text-cn-danger-text' : cx('border border-cn-border-strong', LANE_STYLE[lane.id]),
                            selected && 'border-2 border-cn-accent-border',
                            lockedNow && 'cursor-not-allowed opacity-60',
                            muted[lane.id] && 'opacity-50',
                            lit.has(block.id) && 'motion-safe:animate-cn-highlight motion-reduce:outline motion-reduce:outline-2 motion-reduce:outline-cn-accent',
                          )}
                          style={{ left: pct(block.start), width: `calc(${pct(block.end - block.start)} - 2px)` }}
                        >
                          {lockedNow && <Lock aria-hidden className="size-3 shrink-0" />}
                          {!block.cut && <span className="truncate">{block.label}</span>}
                        </button>
                      );
                    })}
                </div>
              ))}
            </div>
            <span aria-hidden className="pointer-events-none absolute inset-y-0 z-cn-raised w-0.5 bg-cn-accent" style={{ left: pct(playhead) }}>
              <span className="absolute -left-1 top-0 size-2.5 rounded-cn-xs bg-cn-accent" />
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
