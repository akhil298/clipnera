'use client';

import { MessageSquarePlus, Play } from 'lucide-react';
import { type CSSProperties, type ReactNode, useCallback, useEffect, useRef, useState } from 'react';

import { Button, Portal } from '@/components/ui';
import { useLayer } from '@/lib/design/layers';
import { cx, floatingSurface } from '@/lib/design/styles';
import { parseTimecode } from '@/lib/design/timecode';

import { firstTimecodeIn } from './citations';

export interface SelectToActProps {
  children: ReactNode;
  /** Project frame rate, to read the `data-cite-frame` CitedText puts on each chip. */
  fps: number;
  /** "Add to prompt": quote the selected text in the composer (iterate). */
  onAddToPrompt: (text: string) => void;
  /** "Show in video": seek to the first moment the selection names (verify). */
  onShowInVideo: (seconds: number) => void;
  className?: string;
}

interface Picked {
  text: string;
  seconds: number | null;
  style: CSSProperties;
  below: boolean;
}

const EDGE = 120;
const GAP = 8;

/** The first cited moment inside the selection: a chip it crosses, else a bare timecode in the text. */
function momentIn(range: Range, root: HTMLElement, text: string, fps: number): number | null {
  for (const element of root.querySelectorAll<HTMLElement>('[data-cite-frame]')) {
    if (range.intersectsNode(element)) return Number(element.dataset.citeFrame) / fps;
  }
  const code = firstTimecodeIn(text);
  return code ? parseTimecode(code) : null;
}

/**
 * Select text in a reply to get a small floating bar: **Add to prompt** · **Show in video**
 * (07 §6.3). Wrap each assistant reply (or the whole thread) in it.
 */
export function SelectToAct({ children, fps, onAddToPrompt, onShowInVideo, className }: SelectToActProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [picked, setPicked] = useState<Picked | null>(null);
  const close = useCallback(() => setPicked(null), []);
  useLayer(picked !== null, close);

  useEffect(() => {
    const read = () => {
      const root = rootRef.current;
      const selection = window.getSelection();
      if (!root || !selection || selection.isCollapsed || selection.rangeCount === 0) return setPicked(null);
      const range = selection.getRangeAt(0);
      const text = selection.toString().trim();
      if (!text || !root.contains(range.commonAncestorContainer)) return setPicked(null);
      const rect = range.getBoundingClientRect();
      const below = rect.top < 56;
      const left = Math.min(Math.max(rect.left + rect.width / 2, EDGE), window.innerWidth - EDGE);
      setPicked({
        text,
        seconds: momentIn(range, root, text, fps),
        below,
        style: { position: 'fixed', left, top: below ? rect.bottom + GAP : rect.top - GAP },
      });
    };
    document.addEventListener('selectionchange', read);
    window.addEventListener('scroll', close, true);
    return () => {
      document.removeEventListener('selectionchange', read);
      window.removeEventListener('scroll', close, true);
    };
  }, [fps, close]);

  const act = (run: () => void) => {
    run();
    window.getSelection()?.removeAllRanges();
    setPicked(null);
  };

  return (
    <div ref={rootRef} className={className}>
      {children}
      {picked && (
        <Portal>
          <div
            role="toolbar"
            aria-label="Selected text"
            style={picked.style}
            // Keep the text selected while pressing a button.
            onPointerDown={(event) => event.preventDefault()}
            className={cx('z-cn-popover flex -translate-x-1/2 gap-1 p-1', !picked.below && '-translate-y-full', floatingSurface)}
          >
            <Button size="sm" variant="ghost" leadingIcon={<MessageSquarePlus />} onClick={() => act(() => onAddToPrompt(picked.text))}>
              Add to prompt
            </Button>
            {picked.seconds !== null && (
              <Button size="sm" variant="ghost" leadingIcon={<Play />} onClick={() => act(() => onShowInVideo(picked.seconds ?? 0))}>
                Show in video
              </Button>
            )}
          </div>
        </Portal>
      )}
    </div>
  );
}
