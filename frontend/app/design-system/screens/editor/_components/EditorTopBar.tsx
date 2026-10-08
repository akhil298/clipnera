'use client';

import { ChevronLeft, Download, History, Keyboard, Redo2, Share2, Undo2 } from 'lucide-react';

import { type ActivityItem, ActivityIndicator, Button, IconButton } from '@/components/ui';
import { ScoreRing } from '@/components/ui/ScoreRing';
import { cx, focusRing } from '@/lib/design/styles';

import { CLIP, PROJECT } from './sample';

export interface EditorTopBarProps {
  versionCount: number;
  /** Increments when a version is added: the count pulses once (01 §10). */
  versionPulse: number;
  saveState: 'saved' | 'saving' | 'offline';
  activity: ReadonlyArray<ActivityItem>;
  balance: number;
  onHistory: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onExport: () => void;
  onShare: () => void;
  onShortcuts: () => void;
  compact?: boolean;
}

/**
 * Editor top bar (48 px, `z-cn-sticky`). Undo sits here and on the result
 * message (01 §3.4). Export is secondary in the Editor: the one amber action
 * on this screen is the prompt's Send.
 */
export function EditorTopBar({ versionCount, versionPulse, saveState, activity, balance, onHistory, onUndo, onRedo, onExport, onShare, onShortcuts, compact = false }: EditorTopBarProps) {
  return (
    <header className="z-cn-sticky flex h-12 shrink-0 items-center gap-1.5 border-b border-cn-border bg-cn-surface px-2 sm:gap-2 sm:px-3">
      <a href="#clips" className={cx('inline-flex h-8 items-center gap-1 rounded-cn-sm px-1.5 text-cn-label font-semibold text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg', focusRing)}>
        <ChevronLeft aria-hidden className="size-4" />
        {!compact && 'Clips'}
      </a>
      {!compact && <ScoreRing score={88} className="relative size-7" />}
      <div className="min-w-0 flex-1">
        <p className="truncate text-cn-label font-semibold text-cn-fg">{CLIP.title}</p>
        <p className="truncate text-cn-caption text-cn-fg-muted">
          {compact ? (saveState === 'saved' ? 'Saved' : saveState === 'saving' ? 'Saving' : 'Offline · changes kept') : `${PROJECT.title} · clip ${CLIP.index} of ${CLIP.total} · ${saveState === 'saved' ? 'Saved' : saveState === 'saving' ? 'Saving' : 'Offline · changes kept on this device'}`}
        </p>
      </div>
      <IconButton size="sm" label="Undo (⌘Z)" icon={<Undo2 />} onClick={onUndo} />
      {!compact && <IconButton size="sm" label="Redo (⇧⌘Z)" icon={<Redo2 />} onClick={onRedo} />}
      <button
        type="button"
        onClick={onHistory}
        aria-label={`Version history, ${versionCount} versions`}
        className={cx('inline-flex h-8 items-center gap-1.5 rounded-cn-sm px-2 text-cn-label text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg', focusRing)}
      >
        <History aria-hidden className="size-4" />
        {/* Remounts on each new version, so the count pops once (CSS motion, none under reduced motion). */}
        <span key={versionPulse} className={cx('font-cn-mono tabular-nums', versionPulse > 0 && 'motion-safe:animate-in motion-safe:zoom-in-110 motion-safe:duration-cn-slow')}>
          {versionCount}
        </span>
      </button>
      {!compact && <ActivityIndicator items={activity} />}
      {!compact && <span className="hidden font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted xl:inline">{balance.toLocaleString('en-IN')} credits</span>}
      {!compact && <IconButton size="sm" label="Keyboard shortcuts (?)" icon={<Keyboard />} onClick={onShortcuts} />}
      {!compact && (
        <Button size="sm" variant="ghost" leadingIcon={<Share2 />} onClick={onShare}>
          Share
        </Button>
      )}
      <Button size="sm" variant="secondary" leadingIcon={<Download />} onClick={onExport}>
        Export
      </Button>
    </header>
  );
}
