'use client';

import { type KeyboardEvent, type MouseEvent, useEffect, useId, useRef, useState } from 'react';

import { cx, floatingSurface, focusRing } from '@/lib/design/styles';
import { formatTimecode, spokenDuration } from '@/lib/design/timecode';
import { useAnchoredPosition } from '@/lib/design/useAnchoredPosition';
import { delay } from '@/lib/design/tokens';
import { useLayer } from '@/lib/design/layers';

import { Portal } from './Portal';

export interface Citation {
  /** Seconds into the source or project. */
  start: number;
  /** Range end, when the citation spans a range. */
  end?: number;
  /** The transcript line it points at. */
  quote?: string;
  /** Frame at `start`. Decorative. */
  thumbnail?: string;
}

export interface CitationChipProps {
  citation: Citation;
  /** More citations in the same sentence, shown as "+2" (07 §6.3). */
  more?: number;
  /** Click or Enter: seek the player (playback does not start). */
  onSeek: (seconds: number) => void;
  /** Shift-click or Shift+Enter: attach the range as a ContextChip. */
  onAttach?: (citation: Citation) => void;
  /** Hover or focus: the caller marks the range on the timeline ruler. */
  onPreviewChange?: (citation: Citation | null) => void;
  className?: string;
}

/**
 * An inline timecode citation (07 §6.3): Perplexity's numbered sources become
 * moments in the video. Hover (150 ms) or focus shows the frame and the line;
 * click seeks, Shift-click adds the range to the prompt.
 */
export function CitationChip({ citation, more = 0, onSeek, onAttach, onPreviewChange, className }: CitationChipProps) {
  const id = useId();
  const anchorRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const { start, end, quote, thumbnail } = citation;
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [active, setActive] = useState(false);
  useEffect(() => () => clearTimeout(timer.current), []);
  const { style } = useAnchoredPosition(active, anchorRef, panelRef, { side: 'top', align: 'center', offset: 6 });

  const text = end !== undefined ? `${formatTimecode(start)}–${formatTimecode(end)}` : formatTimecode(start);
  const name = `Moment at ${spokenDuration(start)}${end !== undefined ? ` to ${spokenDuration(end)}` : ''}${more ? `, and ${more} more` : ''}`;

  const act = (shift: boolean) => (shift && onAttach ? onAttach(citation) : onSeek(start));
  const preview = (on: boolean) => {
    onPreviewChange?.(on ? citation : null);
    clearTimeout(timer.current);
    if (on) timer.current = setTimeout(() => setActive(true), delay.mediaHover);
    else setActive(false);
  };
  // Escape hides the preview without moving focus (WCAG 1.4.13).
  useLayer(active, () => setActive(false));

  return (
    <>
      <button
        ref={anchorRef}
        type="button"
        aria-label={name}
        aria-describedby={active ? id : undefined}
        onClick={(event: MouseEvent) => act(event.shiftKey)}
        onKeyDown={(event: KeyboardEvent) => {
          if (event.key === 'Enter' && event.shiftKey) {
            event.preventDefault();
            act(true);
          }
        }}
        onPointerEnter={() => preview(true)}
        onPointerLeave={() => preview(false)}
        onFocus={() => preview(true)}
        onBlur={() => preview(false)}
        className={cx(
          'mx-0.5 inline-flex h-5 items-center gap-1 rounded-cn-xs bg-cn-surface-active px-1 align-middle font-cn-mono text-cn-caption tabular-nums text-cn-fg-secondary',
          'transition-colors duration-cn-fast ease-cn-standard hover:bg-cn-accent-subtle hover:text-cn-accent-text',
          active && 'bg-cn-accent-subtle text-cn-accent-text',
          focusRing,
          className,
        )}
      >
        {text}
        {more > 0 && <span className="text-cn-fg-muted">+{more}</span>}
      </button>
      {active && (thumbnail || quote) && (
        <Portal>
          <div ref={panelRef} id={id} role="tooltip" style={style} className={cx('z-cn-popover flex w-72 flex-col gap-2 p-2', floatingSurface)}>
            {thumbnail && <img src={thumbnail} alt="" className="cn-media-edge aspect-video w-full rounded-cn-md object-cover" />}
            {quote && <p className="text-cn-label text-cn-fg">“{quote}”</p>}
            <p className="text-cn-caption text-cn-fg-muted">
              Play from <span className="font-cn-mono tabular-nums">{formatTimecode(start)}</span> ↵{onAttach && ' · ⇧ adds it to the prompt'}
            </p>
          </div>
        </Portal>
      )}
    </>
  );
}
