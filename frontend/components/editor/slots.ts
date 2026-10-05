/**
 * The two typed seams between Wave 6 areas inside the editor (frontend.md §8.4). Shared contract:
 * Area 4 hosts both, Area 8 implements the export dialog, Area 6 produces drops and Area 5 accepts
 * them. Change only with all four owners.
 */
import type { ComponentType } from 'react';

import type { Asset, Timeline } from '@/lib/editor/timeline';

// --- Seam 1: export dialog (Area 8 component, rendered by Area 4's editor) ---

export interface ExportDialogSlotProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** EditorProjectSummary.id (backend/editor/schema.py). */
  projectId: string;
  title: string;
  /** The server version to export. Pending local ops are never exported; Area 4 flushes them first. */
  version: number;
  /** That version's timeline, for aspect, length and the summary the dialog shows. */
  timeline: Timeline;
}

export type ExportDialogSlot = ComponentType<ExportDialogSlotProps>;

// --- Seam 2: B-roll library → timeline (Area 6/7 drag source, Area 5 drop target) ---

/** DataTransfer type for a B-roll drag. Plain-text fallbacks are not read. */
export const BROLL_DRAG_MIME = 'application/x-clipnera-broll+json';

/**
 * What the library knows about the dragged clip: a subset of BrollAssetResponse (backend/broll/schema.py),
 * wire names kept. Area 5 turns it into `add_asset` + `add_item` timeline ops at the drop point.
 */
export interface BrollDropPayload {
  v: 1;
  /** Platform library or the user's own uploads. */
  library: 'platform' | 'mine';
  id: string;
  title: string;
  media: Extract<Asset['kind'], 'video' | 'image'>;
  duration_s: number;
  width: number;
  height: number;
  thumb_url: string | null;
  proxy_url: string | null;
  attribution_text: string | null;
  /** Optional sub-range of the source the user picked, in seconds. */
  range?: { start_s: number; end_s: number };
}

/** Where a drop or an "Add to timeline" button lands: a track id and a frame (Timeline time is whole frames). */
export interface TimelineDropPoint {
  track: string;
  at: number;
}

/** Inserts without a drag (keyboard, "Add to timeline"); Area 5 picks the point when `at` is omitted. */
export type InsertBroll = (payload: BrollDropPayload, at?: TimelineDropPoint) => void;

export function writeBrollDrag(data: DataTransfer, payload: BrollDropPayload): void {
  data.setData(BROLL_DRAG_MIME, JSON.stringify(payload));
  data.effectAllowed = 'copy';
}

/** The payload, or null when the drag is not a B-roll drag or not this contract version. */
export function readBrollDrag(data: DataTransfer): BrollDropPayload | null {
  const raw = data.getData(BROLL_DRAG_MIME);
  if (!raw) return null;
  try {
    const payload = JSON.parse(raw) as Partial<BrollDropPayload>;
    return payload.v === 1 && typeof payload.id === 'string' ? (payload as BrollDropPayload) : null;
  } catch {
    return null;
  }
}
