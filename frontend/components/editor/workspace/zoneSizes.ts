import type { ResizablePanel } from '@/components/ui/ResizablePanels';
import { layout } from '@/lib/design/tokens';

import type { Arrangement } from './useArrangement';

/** A zone's size in px (07 §5.4); `ResizablePanels` works in percent of its group, so these are converted per measure. */
export interface PxBounds {
  size: number;
  min: number;
  max: number;
}

type Bounds = Pick<ResizablePanel, 'defaultSize' | 'minSize' | 'maxSize'>;

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

/**
 * Percent bounds for a sized zone and the flexible partner beside it, inside a group `total` px long.
 * The partner keeps at least `partnerMin` px (the preview's 480).
 */
export function pairBounds(total: number, zone: PxBounds, partnerMin: number): { zone: Bounds; partner: Bounds } {
  const pct = (px: number) => clamp((px / total) * 100, 1, 99);
  const max = Math.max(1, Math.min(pct(zone.max), 100 - pct(partnerMin)));
  const min = Math.min(pct(zone.min), max);
  const size = clamp(pct(zone.size), min, max);
  return {
    zone: { defaultSize: size, minSize: min, maxSize: max },
    partner: { defaultSize: 100 - size, minSize: 100 - max, maxSize: 100 - min },
  };
}

export const PANEL: PxBounds = { size: layout['editor-panel'], min: layout['editor-panel-min'], max: layout['editor-panel-max'] };

export const conversationPx = (arrangement: Arrangement): PxBounds => ({
  size: arrangement === 'lg' ? layout['editor-conversation-min'] : layout['editor-conversation'],
  min: layout['editor-conversation-min'],
  max: layout['editor-conversation-max'],
});

/** Timeline height: 256 (200 at 1024–1279), at least 160, at most half the column. */
export const timelinePx = (arrangement: Arrangement, total: number): PxBounds => ({
  size: arrangement === 'lg' || arrangement === 'md' ? 200 : layout['editor-timeline'],
  min: layout['editor-timeline-min'],
  max: total / 2,
});

/** The rail plus the preview's minimum: what the main column needs beside the conversation. */
export const MAIN_MIN = layout['editor-tool-rail'] + layout['editor-preview-min'];
export const PREVIEW_MIN = layout['editor-preview-min'];
