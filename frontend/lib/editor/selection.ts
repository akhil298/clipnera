/**
 * What the person is pointing at, and the context chips it puts on the composer
 * ("point, then prompt", 02-editor.md §3.6). Selections hold frames and ids; chips are derived:
 * `toContext` for the UI's ContextChip, `toWireChip` for POST /runs (openapi ContextChip).
 */
import { useStore } from 'zustand';
import { createStore, type StoreApi } from 'zustand/vanilla';

import type { PromptContext } from '@/components/ui/ContextChip';
import type { Bbox, WireChip } from '@/lib/api/editor/types';
import { formatTimecode } from '@/lib/design/timecode';

export type Selection =
  /** A timeline item (video or B-roll clip, text, music). `label` is "03 · Hot take"; `meta` "7s". */
  | { kind: 'item'; itemId: string; label: string; meta?: string; thumbnailUrl?: string }
  /** Frames, end exclusive, from the timeline or the transcript. */
  | { kind: 'range'; start: number; end: number }
  | { kind: 'caption'; start: number; end: number; text: string }
  | { kind: 'asset'; assetId: string; library: 'media' | 'broll'; label: string; meta?: string; thumbnailUrl?: string }
  | { kind: 'moment'; frame: number }
  /** NEEDS-BACKEND: EB-9 (chip type `region`). */
  | { kind: 'region'; frame: number; bbox: Bbox };

export interface Chip extends PromptContext {
  /** A running step holds this item; the chip can't be removed until the step ends. */
  locked: boolean;
}

/** One key per selected thing, so selecting it twice doesn't add a second chip. */
export function selectionKey(sel: Selection): string {
  switch (sel.kind) {
    case 'item':
      return `item:${sel.itemId}`;
    case 'range':
      return `range:${sel.start}-${sel.end}`;
    case 'caption':
      return `caption:${sel.start}-${sel.end}`;
    case 'asset':
      return `asset:${sel.library}:${sel.assetId}`;
    case 'moment':
      return `moment:${sel.frame}`;
    case 'region':
      return `region:${sel.frame}:${sel.bbox.x},${sel.bbox.y},${sel.bbox.w},${sel.bbox.h}`;
  }
}

const time = (frame: number, fps: number) => formatTimecode(frame / fps);
const quoted = (text: string) => `“${text.length > 40 ? `${text.slice(0, 39).trimEnd()}…` : text}”`;

/** The chip the composer shows. Regions show as a moment ("Area at 0:14") until ContextChip has a region kind. */
export function toContext(sel: Selection, fps: number): PromptContext {
  const id = selectionKey(sel);
  switch (sel.kind) {
    case 'item':
      return { id, kind: 'clip', label: sel.label, meta: sel.meta, thumbnailUrl: sel.thumbnailUrl };
    case 'range':
      return { id, kind: 'range', label: `${time(sel.start, fps)} – ${time(sel.end, fps)}` };
    case 'caption':
      return { id, kind: 'caption', label: quoted(sel.text) };
    case 'asset':
      return { id, kind: 'asset', label: sel.label, meta: sel.meta, thumbnailUrl: sel.thumbnailUrl };
    case 'moment':
      return { id, kind: 'moment', label: time(sel.frame, fps) };
    case 'region':
      return { id, kind: 'moment', label: `Area at ${time(sel.frame, fps)}` };
  }
}

export function toWireChip(sel: Selection, fps: number): WireChip {
  const label = toContext(sel, fps).label.slice(0, 120);
  switch (sel.kind) {
    case 'item':
      return { type: 'clip', ref: { item_id: sel.itemId }, label };
    case 'range':
      return { type: 'range', ref: { start_frame: sel.start, end_frame: sel.end }, label };
    case 'caption':
      return { type: 'caption_line', ref: { start_frame: sel.start, end_frame: sel.end, text: sel.text }, label };
    case 'asset':
      return { type: 'asset', ref: sel.library === 'broll' ? { broll_asset_id: sel.assetId } : { media_asset_id: sel.assetId }, label };
    case 'moment':
      return { type: 'moment', ref: { frame: sel.frame }, label };
    case 'region':
      return { type: 'region', ref: { frame: sel.frame, bbox: sel.bbox }, label };
  }
}

const WIRE_KIND: Record<WireChip['type'], PromptContext['kind']> = {
  clip: 'clip',
  range: 'range',
  caption_line: 'caption',
  asset: 'asset',
  moment: 'moment',
  region: 'moment',
};

/** A chip echoed by the server (`run.acknowledged`, run snapshots), read-only in the turn heading. */
export function contextFromWire(chip: WireChip, index = 0): PromptContext {
  return { id: `${chip.type}:${index}:${JSON.stringify(chip.ref)}`, kind: WIRE_KIND[chip.type] ?? 'clip', label: chip.label ?? '' };
}

/* ───────────── store ───────────── */

export interface SelectionState {
  /** In the order they were picked. */
  selected: Selection[];
}

export interface SelectionStore {
  store: StoreApi<SelectionState>;
  /** Replace the selection; `additive` (⌘-click) adds or, if already there, removes it. */
  select(sel: Selection, options?: { additive?: boolean }): void;
  remove(key: string): void;
  clear(): void;
  /** Drop selections whose items no longer exist (after a rebase or a run removed them). */
  prune(itemExists: (itemId: string) => boolean): void;
}

export function reduceSelect(selected: Selection[], sel: Selection, additive: boolean): Selection[] {
  const key = selectionKey(sel);
  const present = selected.some((s) => selectionKey(s) === key);
  if (!additive) return [sel];
  return present ? selected.filter((s) => selectionKey(s) !== key) : [...selected, sel];
}

export function createSelectionStore(): SelectionStore {
  const store = createStore<SelectionState>(() => ({ selected: [] }));
  return {
    store,
    select: (sel, options) => store.setState((s) => ({ selected: reduceSelect(s.selected, sel, Boolean(options?.additive)) })),
    remove: (key) => store.setState((s) => ({ selected: s.selected.filter((sel) => selectionKey(sel) !== key) })),
    clear: () => store.setState({ selected: [] }),
    prune: (itemExists) =>
      store.setState((s) => {
        const kept = s.selected.filter((sel) => sel.kind !== 'item' || itemExists(sel.itemId));
        return kept.length === s.selected.length ? s : { selected: kept };
      }),
  };
}

export const selectSelected = (s: SelectionState): Selection[] => s.selected;
export const selectIsSelected = (key: string) => (s: SelectionState): boolean => s.selected.some((sel) => selectionKey(sel) === key);
/** Chips for the composer; locked when a running step holds the item (pass the run store's `isLocked`). */
export function chipsFor(selected: Selection[], fps: number, isLocked: (itemId: string) => boolean = () => false): Chip[] {
  return selected.map((sel) => ({ ...toContext(sel, fps), locked: sel.kind === 'item' && isLocked(sel.itemId) }));
}

/** React binding. `selectSelected` is stable; build chips with `useMemo(() => chipsFor(...))`. */
export function useSelection<T>(selection: SelectionStore, selector: (state: SelectionState) => T): T {
  return useStore(selection.store, selector);
}
