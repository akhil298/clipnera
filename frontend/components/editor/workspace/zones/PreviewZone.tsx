'use client';

/**
 * Z2 preview slot. Filled by P2 (stage, aspect, safe zones, transport, quality badge, states) and
 * P3 (select-to-edit, inside it). The frame draws the `stage` surface; this fills it.
 *
 * Props contract (stable):
 * - `placement`: `stage` (desktop and tablet zone; the docked composer may sit under it at 768–1023)
 *   or `phone` (full width at the top, a 9:16 clip letterboxed at up to 45svh, 16:9 at 203 px).
 * From `useEditor()`: `engine` (mount it with `engine.mount(el)` / `engine.unmount()`; the frame owns
 * creating, retiming via `setTimeline` and destroying it), `doc` (`selectShown`, `selectReadOnly`,
 * `selectLanded`), `selection`, `features.timeline` (false → the read-only stand-in).
 */
import { MonitorPlay } from 'lucide-react';

import { TimeCode } from '@/components/ui/TimeCode';
import { selectDurationFrames, selectFps, useDoc } from '@/lib/editor/store';

import { useEditor } from '../context';

export type PreviewPlacement = 'stage' | 'phone';

export interface PreviewZoneProps {
  placement: PreviewPlacement;
}

export function PreviewZone({ placement }: PreviewZoneProps) {
  const { doc } = useEditor();
  const frames = useDoc(doc, selectDurationFrames);
  const fps = useDoc(doc, selectFps);
  return (
    <div data-theme="dark" className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 p-4 text-center text-cn-fg-secondary">
      <MonitorPlay aria-hidden className={placement === 'phone' ? 'size-6' : 'size-8'} />
      <p className="text-cn-label">Preview</p>
      <TimeCode seconds={frames / fps} tone="muted" />
    </div>
  );
}
