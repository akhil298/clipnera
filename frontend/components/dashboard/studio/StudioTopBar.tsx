"use client";
import React, { useEffect, useRef } from 'react';
import {
  ArrowLeft,
  CalendarDays,
  Check,
  ChevronDown,
  CloudOff,
  Download,
  Keyboard,
  LayoutGrid,
  Loader2,
  Redo2,
  Undo2,
} from 'lucide-react';
import { AspectRatio } from '@/lib/types';
import { ProLockBadge } from '../ProLockBadge';
import { Switch } from './controls';
import { EXPORT_SIZE } from './studioUtils';
import type { StudioLayout } from './useStudioLayout';

export type SaveState = 'idle' | 'pending' | 'saving' | 'saved' | 'error';

interface StudioTopBarProps {
  layout: StudioLayout;
  title: string;
  subtitle: string;
  score: number;
  aspectRatio: AspectRatio;
  saveState: SaveState;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
  onBack: () => void;
  onOpenClips: () => void;
  clipCount: number;
  onShowShortcuts: () => void;
  menuOpen: boolean;
  onMenuOpenChange: (open: boolean) => void;
  onExport: () => void;
  onSchedule: () => void;
  watermarkOn: boolean;
  watermarkForced: boolean;
  onToggleWatermark: () => void;
}

function SaveIndicator({ state }: { state: SaveState }) {
  if (state === 'pending' || state === 'saving') {
    return (
      <span role="status" className="inline-flex items-center gap-1.5 text-xs text-neutral-400 whitespace-nowrap">
        <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />
        Saving
      </span>
    );
  }
  if (state === 'error') {
    return (
      <span role="status" className="inline-flex items-center gap-1.5 text-xs text-rose-300 whitespace-nowrap" title="Check your connection. Your next change will retry.">
        <CloudOff className="w-3.5 h-3.5" aria-hidden />
        Not saved
      </span>
    );
  }
  return (
    <span role="status" className="inline-flex items-center gap-1.5 text-xs text-neutral-400 whitespace-nowrap">
      <Check className="w-3.5 h-3.5 text-emerald-400" aria-hidden />
      {state === 'saved' ? 'Saved' : 'Autosave on'}
    </span>
  );
}

const iconButton =
  'w-8 h-8 shrink-0 rounded-[9px] inline-flex items-center justify-center text-neutral-400 hover:bg-neutral-800 hover:text-white disabled:opacity-35 disabled:hover:bg-transparent disabled:hover:text-neutral-400';

export function StudioTopBar(props: StudioTopBarProps) {
  const {
    layout, title, subtitle, score, aspectRatio, saveState, canUndo, canRedo, onUndo, onRedo, onBack,
    onOpenClips, clipCount, onShowShortcuts, menuOpen, onMenuOpenChange, onExport, onSchedule,
    watermarkOn, watermarkForced, onToggleWatermark,
  } = props;
  const menuRef = useRef<HTMLDivElement>(null);
  const phone = layout === 'phone';

  useEffect(() => {
    if (!menuOpen) return;
    const onPointer = (e: PointerEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) onMenuOpenChange(false);
    };
    window.addEventListener('pointerdown', onPointer);
    return () => window.removeEventListener('pointerdown', onPointer);
  }, [menuOpen, onMenuOpenChange]);

  const menu = menuOpen && (
    <div
      role="menu"
      className="absolute right-0 top-[42px] z-40 w-[290px] rounded-2xl border border-neutral-700 bg-neutral-900 p-1.5 shadow-2xl shadow-black/60"
    >
      <button
        type="button"
        role="menuitem"
        onClick={() => {
          onMenuOpenChange(false);
          onExport();
        }}
        className="flex w-full items-center gap-3 rounded-xl p-2.5 text-left hover:bg-neutral-800"
      >
        <span className="w-8 h-8 shrink-0 rounded-[9px] bg-neutral-800 flex items-center justify-center text-amber-400">
          <Download className="w-4 h-4" aria-hidden />
        </span>
        <span>
          <b className="block text-[13px] text-white">Download HD</b>
          <small className="text-[11.5px] text-neutral-400">MP4 · {EXPORT_SIZE[aspectRatio]}</small>
        </span>
      </button>
      <button
        type="button"
        role="menuitem"
        onClick={() => {
          onMenuOpenChange(false);
          onSchedule();
        }}
        className="flex w-full items-center gap-3 rounded-xl p-2.5 text-left hover:bg-neutral-800"
      >
        <span className="w-8 h-8 shrink-0 rounded-[9px] bg-neutral-800 flex items-center justify-center text-amber-400">
          <CalendarDays className="w-4 h-4" aria-hidden />
        </span>
        <span>
          <b className="block text-[13px] text-white">Schedule post</b>
          <small className="text-[11.5px] text-neutral-400">Pick a time and platforms</small>
        </span>
      </button>
      <div className="my-1.5 mx-1 h-px bg-neutral-800" />
      <div className="flex items-center justify-between gap-3 px-2.5 py-2 text-[12.5px] text-white">
        <span>
          <span className="flex items-center gap-1.5">
            Clipnera watermark
            {watermarkForced && <ProLockBadge feature="Removing the watermark" />}
          </span>
          <small className="block text-[11px] text-neutral-500">
            {watermarkForced ? 'Paid plans can turn it off' : 'Shown in the exported video'}
          </small>
        </span>
        <Switch checked={watermarkOn || watermarkForced} onChange={onToggleWatermark} label="Clipnera watermark" />
      </div>
    </div>
  );

  const exportControl = (
    <div ref={menuRef} className="relative flex shrink-0">
      <button
        type="button"
        onClick={phone ? () => onMenuOpenChange(!menuOpen) : onExport}
        aria-haspopup={phone ? 'menu' : undefined}
        aria-expanded={phone ? menuOpen : undefined}
        title={phone ? undefined : 'Export HD (⌘E)'}
        className={`h-[34px] px-3.5 inline-flex items-center gap-1.5 bg-amber-500 hover:bg-amber-400 text-neutral-950 text-[13px] font-extrabold ${
          phone ? 'rounded-[10px]' : 'rounded-l-[10px]'
        }`}
      >
        <Download className="w-[15px] h-[15px]" aria-hidden />
        Export
      </button>
      {!phone && (
        <button
          type="button"
          onClick={() => onMenuOpenChange(!menuOpen)}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          aria-label="More export options"
          className="h-[34px] w-[30px] rounded-r-[10px] inline-flex items-center justify-center bg-amber-500 hover:bg-amber-400 text-neutral-950 border-l border-black/25"
        >
          <ChevronDown className="w-4 h-4" aria-hidden />
        </button>
      )}
      {menu}
    </div>
  );

  if (phone) {
    return (
      <header className="h-[52px] shrink-0 flex items-center gap-1.5 pl-1 pr-2 border-b border-neutral-800 bg-neutral-900">
        <button type="button" onClick={onBack} className={iconButton} aria-label="Back to clips">
          <ArrowLeft className="w-4 h-4" aria-hidden />
        </button>
        <div className="flex-1 min-w-0">
          <strong className="block truncate text-[13.5px] font-bold text-white">{title}</strong>
          <SaveIndicator state={saveState} />
        </div>
        <button type="button" onClick={onUndo} disabled={!canUndo} className={iconButton} aria-label="Undo">
          <Undo2 className="w-4 h-4" aria-hidden />
        </button>
        {exportControl}
      </header>
    );
  }

  return (
    <header className="h-14 flex items-center gap-2.5 px-3.5 min-w-0 border-b border-neutral-800 bg-neutral-900 [grid-area:top]">
      <button
        type="button"
        onClick={onBack}
        className="h-8 shrink-0 inline-flex items-center gap-1.5 pl-1.5 pr-2.5 rounded-[9px] text-sm font-semibold text-neutral-400 hover:bg-neutral-800 hover:text-white"
        title="Back to clips (Esc)"
      >
        <ArrowLeft className="w-4 h-4" aria-hidden />
        Clips
      </button>
      <span className="w-px h-[22px] bg-neutral-800 shrink-0" />
      {layout === 'tablet' && clipCount > 1 && (
        <button
          type="button"
          onClick={onOpenClips}
          className="h-[30px] shrink-0 inline-flex items-center gap-1.5 px-2.5 rounded-[9px] border border-neutral-800 bg-neutral-900 text-xs font-semibold text-neutral-300 hover:text-white"
        >
          <LayoutGrid className="w-3.5 h-3.5" aria-hidden />
          Clips {clipCount}
        </button>
      )}
      <span
        className="shrink-0 w-[30px] h-[30px] rounded-full flex items-center justify-center text-[11px] font-extrabold text-amber-300 tabular-nums"
        style={{
          background: `radial-gradient(closest-side, #171717 76%, transparent 78% 100%), conic-gradient(#f59e0b ${Math.max(0, Math.min(100, score))}%, #262626 0)`,
        }}
        title="Viral score"
      >
        {score}
      </span>
      <div className="min-w-0 flex flex-col">
        <small className="truncate text-[11px] text-neutral-500">{subtitle}</small>
        <strong className="truncate text-sm font-bold text-white">{title}</strong>
      </div>
      <div className="flex-1 min-w-0" />
      <button type="button" onClick={onUndo} disabled={!canUndo} className={iconButton} aria-label="Undo" title="Undo (⌘Z)">
        <Undo2 className="w-4 h-4" aria-hidden />
      </button>
      <button type="button" onClick={onRedo} disabled={!canRedo} className={iconButton} aria-label="Redo" title="Redo (⇧⌘Z)">
        <Redo2 className="w-4 h-4" aria-hidden />
      </button>
      <SaveIndicator state={saveState} />
      <span className="w-px h-[22px] bg-neutral-800 shrink-0" />
      {layout === 'desktop' && (
        <button type="button" onClick={onShowShortcuts} className={iconButton} aria-label="Keyboard shortcuts" title="Shortcuts (?)">
          <Keyboard className="w-4 h-4" aria-hidden />
        </button>
      )}
      {exportControl}
    </header>
  );
}
