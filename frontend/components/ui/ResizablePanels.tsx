'use client';

import { type KeyboardEvent, type PointerEvent, type ReactNode, useId, useRef, useState } from 'react';

import { cx } from '@/lib/design/styles';
import { usePersistentState } from '@/lib/design/usePersistentState';

export interface ResizablePanel {
  id: string;
  /** Names the handle after this panel: "Resize Conversation". */
  label: string;
  /** Percent of the group. Defaults should add up to 100. */
  defaultSize: number;
  /** Percent. Default 10. */
  minSize?: number;
  /** Percent. Default 90. */
  maxSize?: number;
  children: ReactNode;
  className?: string;
}

export interface ResizablePanelsProps {
  panels: ReadonlyArray<ResizablePanel>;
  /** `horizontal` puts panels side by side (editor: chat | preview | tools). */
  direction?: 'horizontal' | 'vertical';
  /** Remembers sizes in this browser under this key (`cn-panels:<key>`). Omit to forget on reload. */
  storageKey?: string;
  className?: string;
}

const KEY_STEP = 2;
const KEY_BIG_STEP = 10;

const bounds = (panel: ResizablePanel) => ({ min: panel.minSize ?? 10, max: panel.maxSize ?? 90 });

/**
 * Panels split by draggable handles. Each handle is a focusable
 * `role="separator"` (WAI-ARIA window splitter): ←/→ (↑/↓ when stacked) move it
 * 2%, Shift 10%, Home/End jump to the limits, Enter or a double-click resets.
 * The drag alternative required by WCAG 2.5.7 is the keyboard. Below `lg`,
 * screens should stack or tab their panes instead of rendering this.
 */
export function ResizablePanels({ panels, direction = 'horizontal', storageKey, className }: ResizablePanelsProps) {
  const id = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const defaults = panels.map((panel) => panel.defaultSize);
  const [stored, setStored] = usePersistentState<number[]>(storageKey ? `cn-panels:${storageKey}` : undefined, defaults);
  const [dragging, setDragging] = useState<{ index: number; sizes: number[] } | null>(null);
  const horizontal = direction === 'horizontal';

  const valid = stored.length === panels.length ? stored : defaults;
  const sizes = dragging?.sizes ?? valid;

  /** Moves the boundary after panel `index` so that panel becomes `target`, respecting both neighbours' limits. */
  const resized = (from: number[], index: number, target: number): number[] => {
    const a = bounds(panels[index]);
    const b = bounds(panels[index + 1]);
    const pair = from[index] + from[index + 1];
    const next = Math.min(a.max, pair - b.min, Math.max(a.min, pair - b.max, target));
    const result = [...from];
    result[index] = Number(next.toFixed(2));
    result[index + 1] = Number((pair - next).toFixed(2));
    return result;
  };

  const onPointerDown = (index: number) => (event: PointerEvent<HTMLDivElement>) => {
    const container = containerRef.current;
    if (!container || event.button !== 0) return;
    event.preventDefault();
    event.currentTarget.focus();
    const rect = container.getBoundingClientRect();
    const total = horizontal ? rect.width : rect.height;
    const start = horizontal ? event.clientX : event.clientY;
    const startSizes = valid;
    let latest = startSizes;
    setDragging({ index, sizes: startSizes });
    const previousSelect = document.body.style.userSelect;
    document.body.style.userSelect = 'none';

    const move = (e: globalThis.PointerEvent) => {
      const delta = (((horizontal ? e.clientX : e.clientY) - start) / total) * 100;
      latest = resized(startSizes, index, startSizes[index] + delta);
      setDragging({ index, sizes: latest });
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      window.removeEventListener('pointercancel', up);
      document.body.style.userSelect = previousSelect;
      setDragging(null);
      setStored(latest);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    window.addEventListener('pointercancel', up);
  };

  const onKeyDown = (index: number) => (event: KeyboardEvent<HTMLDivElement>) => {
    const step = event.shiftKey ? KEY_BIG_STEP : KEY_STEP;
    const { min, max } = bounds(panels[index]);
    const keys: Record<string, number> = horizontal
      ? { ArrowLeft: valid[index] - step, ArrowRight: valid[index] + step, Home: min, End: max }
      : { ArrowUp: valid[index] - step, ArrowDown: valid[index] + step, Home: min, End: max };
    if (event.key === 'Enter') {
      event.preventDefault();
      setStored(defaults);
      return;
    }
    if (!(event.key in keys)) return;
    event.preventDefault();
    setStored(resized(valid, index, keys[event.key]));
  };

  return (
    <div ref={containerRef} className={cx('flex min-h-0 min-w-0', horizontal ? 'flex-row' : 'flex-col', className)}>
      {panels.map((panel, index) => {
        const { min, max } = bounds(panel);
        const active = dragging?.index === index;
        return (
          <div key={panel.id} className="contents">
            <div
              id={`${id}-${panel.id}`}
              style={{ flexBasis: `${sizes[index]}%` }}
              className={cx('min-h-0 min-w-0 shrink grow-0 overflow-hidden', panel.className)}
            >
              {panel.children}
            </div>
            {index < panels.length - 1 && (
              <div
                role="separator"
                tabIndex={0}
                aria-label={`Resize ${panel.label}`}
                aria-controls={`${id}-${panel.id}`}
                aria-orientation={horizontal ? 'vertical' : 'horizontal'}
                aria-valuenow={Math.round(sizes[index])}
                aria-valuemin={min}
                aria-valuemax={max}
                onPointerDown={onPointerDown(index)}
                onKeyDown={onKeyDown(index)}
                onDoubleClick={() => setStored(defaults)}
                className={cx(
                  'group relative z-cn-raised flex shrink-0 touch-none items-center justify-center outline-none',
                  horizontal ? '-mx-1 w-2 cursor-col-resize' : '-my-1 h-2 cursor-row-resize',
                )}
              >
                <span
                  aria-hidden
                  className={cx(
                    'rounded-cn-full transition-colors duration-cn-fast',
                    horizontal ? 'h-full w-px' : 'h-px w-full',
                    active
                      ? 'bg-cn-accent'
                      : 'bg-cn-border group-hover:bg-cn-border-strong group-focus-visible:bg-cn-focus',
                    'group-focus-visible:outline group-focus-visible:outline-2 group-focus-visible:outline-offset-1 group-focus-visible:outline-cn-focus',
                  )}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
