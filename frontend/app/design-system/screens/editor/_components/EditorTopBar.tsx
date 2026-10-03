'use client';

import { ChevronLeft, Download, History, Keyboard, Redo2, Share2, Undo2 } from 'lucide-react';
import { motion } from 'framer-motion';

import { Button } from '@/components/ui/Button';
import { IconButton } from '@/components/ui/IconButton';
import { ScoreRing } from '@/components/ui/ScoreRing';
import { cx, focusRing } from '@/lib/design/styles';
import { duration } from '@/lib/design/tokens';
import { useReducedMotion } from '@/lib/design/useReducedMotion';

import { type ActivityJob, ActivityIndicator } from './ActivityIndicator';
import { CLIP, PROJECT } from './sample';

export interface EditorTopBarProps {
  versionCount: number;
  /** Increments when a version is added: the count pulses once (01 §10). */
  versionPulse: number;
  saveState: 'saved' | 'saving' | 'offline';
  jobs: ReadonlyArray<ActivityJob>;
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
 * Editor top bar (56 px, `z-cn-sticky`). Undo sits here and on the result
 * message (01 §3.4). Export is secondary in the Editor: the one amber action
 * on this screen is the prompt's Send.
 */
export function EditorTopBar({ versionCount, versionPulse, saveState, jobs, balance, onHistory, onUndo, onRedo, onExport, onShare, onShortcuts, compact = false }: EditorTopBarProps) {
  const reduced = useReducedMotion();
  return (
    <header className="z-cn-sticky flex h-14 shrink-0 items-center gap-1.5 border-b border-cn-border bg-cn-surface px-2 sm:gap-2 sm:px-3">
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
        <motion.span
          key={versionPulse}
          initial={reduced || versionPulse === 0 ? false : { scale: 1 }}
          animate={reduced ? undefined : { scale: [1, 1.15, 1] }}
          transition={{ duration: duration.slow / 1000 }}
          className="font-cn-mono tabular-nums"
        >
          {versionCount}
        </motion.span>
      </button>
      {!compact && <ActivityIndicator jobs={jobs} />}
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
