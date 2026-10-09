'use client';

/**
 * Z3 timeline slot. Filled by T1 (tracks, ruler, playhead, zoom, read-only) and T2 (edits, AI markers).
 *
 * Props contract (stable):
 * - `placement`: `full` (multi-track zone under the preview, resizable 160 px to half the height),
 *   `compact` (768–1023: same zone, default 200 px) or `strip` (the phone's Timeline tab: one 96 px
 *   story track with "Expand" opening the full view as a sheet).
 * From `useEditor()`: `doc` (`selectTracks`, `selectItem`, `selectReadOnly`, `selectLanded`, `apply`),
 * `runs` (`selectMarkers`, `selectLockedIds`), `selection`, `engine.clock` (playhead: subscribe and
 * write `style.transform`, never React state), `features.timeline`.
 */
import { Rows3 } from 'lucide-react';

import { selectTracks, useDoc } from '@/lib/editor/store';

import { useEditor } from '../context';
import { ZoneNote } from '../Zone';

export type TimelinePlacement = 'full' | 'compact' | 'strip';

export interface TimelineZoneProps {
  placement: TimelinePlacement;
}

export function TimelineZone({ placement }: TimelineZoneProps) {
  const { doc } = useEditor();
  const tracks = useDoc(doc, selectTracks);
  return (
    <ZoneNote
      icon={<Rows3 />}
      title="Timeline"
      description={placement === 'strip' ? undefined : `${tracks.length} ${tracks.length === 1 ? 'track' : 'tracks'} in this edit.`}
    />
  );
}
