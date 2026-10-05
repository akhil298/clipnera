'use client';

import { GripVertical } from 'lucide-react';
import { type CSSProperties, type KeyboardEvent, type PointerEvent, type ReactNode, useRef } from 'react';

import { cx, floatingSurface, focusRing } from '@/lib/design/styles';
import { usePersistentState } from '@/lib/design/usePersistentState';

/** Where a dragged toolbar settles inside its container. */
export type ToolbarSnap = 'anchor' | 'top-left' | 'top-right' | 'bottom-left' | 'bottom-center' | 'bottom-right';

/** A selected element's box, in px relative to the toolbar's positioned container. */
export interface AnchorRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

export interface FloatingToolbarProps {
  /** Toolbar name: "Caption actions". */
  label: string;
  /** Buttons (`size="sm"`); ←/→ move between them. */
  children: ReactNode;
  /** The selected element. Without it, or after a drag, the toolbar sits at its snap point. */
  anchor?: AnchorRect;
  /** Remembers the dragged position (per project): `toolbar:${projectId}`. */
  storageKey?: string;
  /** Escape inside the toolbar. */
  onDismiss?: () => void;
  className?: string;
}

const SNAP_POINTS: ReadonlyArray<Exclude<ToolbarSnap, 'anchor'>> = ['top-left', 'top-right', 'bottom-right', 'bottom-center', 'bottom-left'];
/** Below this distance from the top, an anchored toolbar flips under the element. */
const FLIP_ROOM = 48;
const GAP = 8;

const SNAP_CLASS: Record<Exclude<ToolbarSnap, 'anchor'>, string> = {
  'top-left': 'left-2 top-2',
  'top-right': 'right-2 top-2',
  'bottom-left': 'bottom-2 left-2',
  'bottom-center': 'bottom-2 left-1/2 -translate-x-1/2',
  'bottom-right': 'bottom-2 right-2',
};

function nearestSnap(container: DOMRect, x: number, y: number): Exclude<ToolbarSnap, 'anchor'> {
  const top = y - container.top < container.height / 2;
  const third = (x - container.left) / container.width;
  if (top) return third < 0.5 ? 'top-left' : 'top-right';
  return third < 1 / 3 ? 'bottom-left' : third > 2 / 3 ? 'bottom-right' : 'bottom-center';
}

/**
 * The select-to-edit toolbar over the preview stage (editor §4.1). Anchored
 * above the selected element (below it near the top edge). The grip drags it
 * to a corner or bottom centre, where it stays; arrows on the grip do the
 * same by keyboard. Put it in a `relative` container (the stage).
 */
export function FloatingToolbar({ label, children, anchor, storageKey, onDismiss, className }: FloatingToolbarProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [snap, setSnap] = usePersistentState<ToolbarSnap>(storageKey, 'anchor');
  const placed = snap === 'anchor' && !anchor ? 'bottom-center' : snap;

  const onPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const onPointerUp = (event: PointerEvent<HTMLButtonElement>) => {
    const container = ref.current?.offsetParent?.getBoundingClientRect();
    if (!container || !event.currentTarget.hasPointerCapture(event.pointerId)) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    setSnap(nearestSnap(container, event.clientX, event.clientY));
  };

  const onGripKey = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (!['ArrowUp', 'ArrowDown', 'Home'].includes(event.key)) return;
    event.preventDefault();
    event.stopPropagation();
    if (event.key === 'Home') return setSnap('anchor');
    const at = SNAP_POINTS.indexOf(placed as Exclude<ToolbarSnap, 'anchor'>);
    const step = event.key === 'ArrowDown' ? 1 : -1;
    setSnap(SNAP_POINTS[(at + step + SNAP_POINTS.length) % SNAP_POINTS.length]);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape' && onDismiss) {
      event.preventDefault();
      onDismiss();
      return;
    }
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    const buttons = Array.from(ref.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') ?? []);
    const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (at < 0) return;
    event.preventDefault();
    buttons[(at + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length]?.focus();
  };

  let style: CSSProperties | undefined;
  if (placed === 'anchor' && anchor) {
    const below = anchor.top < FLIP_ROOM;
    style = {
      left: anchor.left + anchor.width / 2,
      top: below ? anchor.top + anchor.height + GAP : anchor.top - GAP,
      transform: `translate(-50%, ${below ? '0' : '-100%'})`,
    };
  }

  return (
    <div
      ref={ref}
      role="toolbar"
      aria-label={label}
      onKeyDown={onKeyDown}
      style={style}
      className={cx(
        'absolute z-cn-popover flex max-w-full items-center gap-0.5 p-1',
        floatingSurface,
        placed !== 'anchor' && SNAP_CLASS[placed],
        'motion-safe:animate-in motion-safe:fade-in motion-safe:duration-cn-base',
        className,
      )}
    >
      <button
        type="button"
        aria-label="Move toolbar. Arrow keys pick a corner, Home puts it back by the selection"
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onKeyDown={onGripKey}
        className={cx('inline-flex h-7 w-5 cursor-grab touch-none items-center justify-center rounded-cn-sm text-cn-fg-muted hover:bg-cn-surface-hover active:cursor-grabbing', focusRing)}
      >
        <GripVertical aria-hidden className="size-3.5" />
      </button>
      {children}
    </div>
  );
}
