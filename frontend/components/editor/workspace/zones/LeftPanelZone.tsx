'use client';

/**
 * Z1 tool panel slot. Filled by X1 (transcript), C1 (captions), H1 (hook, audio, format, sound) and
 * B1 (B-roll): replace the body with a switch on `tool` that renders each unit's panel. The frame
 * never changes for that.
 *
 * Props contract (stable):
 * - `tool`: which tool is open (`EditorToolId`, workspace/tools.tsx).
 * - `placement`: `docked` (resizable column, ≥ 1280), `overlay` (sheet over the preview, 768–1279)
 *   or `tab` (the phone's Media tab, under the tool row). Pad and size for it; the frame draws the surface.
 * - `onClose`: closes the panel (not shown on phones, where the tab stays).
 * Everything else (stores, engine, selection, layout) comes from `useEditor()`.
 */
import { PanelLeft, X } from 'lucide-react';

import { IconButton } from '@/components/ui/IconButton';

import { toolLabel, type EditorToolId, EDITOR_TOOLS } from '../tools';
import { ZoneNote } from '../Zone';

export type PanelPlacement = 'docked' | 'overlay' | 'tab';

export interface LeftPanelZoneProps {
  tool: EditorToolId;
  placement: PanelPlacement;
  onClose: () => void;
}

export function LeftPanelZone({ tool, placement, onClose }: LeftPanelZoneProps) {
  const label = toolLabel(tool);
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {placement !== 'tab' && (
        <div className="flex h-11 shrink-0 items-center gap-2 border-b border-cn-border pl-3 pr-1.5">
          <h2 className="min-w-0 flex-1 truncate text-cn-label font-semibold text-cn-fg">{label}</h2>
          <IconButton size="sm" label={`Close ${label}`} icon={<X />} onClick={onClose} />
        </div>
      )}
      <ZoneNote
        icon={EDITOR_TOOLS.find((item) => item.id === tool)?.icon ?? <PanelLeft />}
        title={label}
        description="Pick a moment on the timeline or ask Clipnera, and the controls for it appear here."
      />
    </div>
  );
}
