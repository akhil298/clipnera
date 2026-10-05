'use client';

import { type CSSProperties, type RefObject, useCallback, useLayoutEffect, useState } from 'react';

export type Side = 'top' | 'bottom' | 'left' | 'right';
export type Align = 'start' | 'center' | 'end';

export interface AnchorOptions {
  side?: Side;
  align?: Align;
  /** Gap between anchor and panel, px. */
  offset?: number;
  /** Make the panel at least as wide as the anchor (select lists, slash menu). */
  matchWidth?: boolean;
}

const VIEWPORT_MARGIN = 8;
const OPPOSITE: Record<Side, Side> = { top: 'bottom', bottom: 'top', left: 'right', right: 'left' };

interface Placement {
  top: number;
  left: number;
  side: Side;
  minWidth?: number;
}

function place(anchor: DOMRect, panel: { width: number; height: number }, side: Side, align: Align, offset: number): Placement {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const fits: Record<Side, boolean> = {
    top: anchor.top - offset - panel.height >= VIEWPORT_MARGIN,
    bottom: anchor.bottom + offset + panel.height <= vh - VIEWPORT_MARGIN,
    left: anchor.left - offset - panel.width >= VIEWPORT_MARGIN,
    right: anchor.right + offset + panel.width <= vw - VIEWPORT_MARGIN,
  };
  const chosen = !fits[side] && fits[OPPOSITE[side]] ? OPPOSITE[side] : side;
  const vertical = chosen === 'top' || chosen === 'bottom';

  const alongStart = vertical ? anchor.left : anchor.top;
  const alongSize = vertical ? anchor.width : anchor.height;
  const panelAlong = vertical ? panel.width : panel.height;
  const along =
    align === 'start' ? alongStart : align === 'end' ? alongStart + alongSize - panelAlong : alongStart + alongSize / 2 - panelAlong / 2;
  const alongMax = (vertical ? vw : vh) - VIEWPORT_MARGIN - panelAlong;
  const clamped = Math.max(VIEWPORT_MARGIN, Math.min(along, alongMax));

  const across = {
    top: anchor.top - offset - panel.height,
    bottom: anchor.bottom + offset,
    left: anchor.left - offset - panel.width,
    right: anchor.right + offset,
  }[chosen];

  return vertical ? { top: across, left: clamped, side: chosen } : { top: clamped, left: across, side: chosen };
}

/**
 * Positions a fixed panel next to its anchor, flipping to the other side when
 * it would leave the viewport and staying 8px inside the edges. Follows scroll
 * in any ancestor, window resize and changes to the panel's own size.
 */
export function useAnchoredPosition(
  open: boolean,
  anchorRef: RefObject<HTMLElement | null>,
  panelRef: RefObject<HTMLElement | null>,
  { side = 'bottom', align = 'start', offset = 6, matchWidth = false }: AnchorOptions = {},
): { style: CSSProperties; side: Side; ready: boolean } {
  const [placement, setPlacement] = useState<Placement | null>(null);

  const update = useCallback(() => {
    const anchor = anchorRef.current;
    const panel = panelRef.current;
    if (!anchor || !panel) return;
    const rect = anchor.getBoundingClientRect();
    const next = place(rect, { width: panel.offsetWidth, height: panel.offsetHeight }, side, align, offset);
    setPlacement(matchWidth ? { ...next, minWidth: rect.width } : next);
  }, [anchorRef, panelRef, side, align, offset, matchWidth]);

  useLayoutEffect(() => {
    if (!open) {
      setPlacement(null);
      return;
    }
    update();
    const observer = new ResizeObserver(update);
    if (panelRef.current) observer.observe(panelRef.current);
    window.addEventListener('scroll', update, true);
    window.addEventListener('resize', update);
    return () => {
      observer.disconnect();
      window.removeEventListener('scroll', update, true);
      window.removeEventListener('resize', update);
    };
  }, [open, update, panelRef]);

  const style: CSSProperties = placement
    ? { position: 'fixed', top: placement.top, left: placement.left, minWidth: placement.minWidth }
    : { position: 'fixed', top: 0, left: 0, visibility: 'hidden' };

  // `ready` turns true once the panel is placed and visible: focus it only then.
  return { style, side: placement?.side ?? side, ready: placement !== null };
}
