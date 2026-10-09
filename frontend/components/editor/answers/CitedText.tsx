'use client';

import { CitationChip, StreamingText } from '@/components/ui';
import type { Citation } from '@/lib/api/editor/types';
import { cx } from '@/lib/design/styles';

import { type FrameRange, hasCitationTokens, splitCited, toChipCitation } from './citations';

/** What every citation in the thread can do. E4a wires these to the player, timeline and composer. */
export interface CitationHandlers {
  /** Project frame rate (doc store `selectFps`). */
  fps: number;
  /** Click / Enter: seek the player, playback does not start. */
  onSeek: (seconds: number) => void;
  /** Shift-click / Shift+Enter: attach the range as a Range chip. */
  onAttachRange?: (range: FrameRange) => void;
  /** Hover / focus: mark the range on the timeline ruler; null clears it. */
  onPreviewChange?: (range: FrameRange | null) => void;
  /** The frame at a time, for the hover preview (P1 thumbnails). */
  posterAt?: (frame: number) => string | undefined;
}

export interface CitedTextProps extends CitationHandlers {
  text: string;
  citations: ReadonlyArray<Citation>;
  streaming?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}

const range = (citation: Citation): FrameRange => ({ start: citation.start_f, end: Math.max(citation.end_f, citation.start_f) });

/**
 * Reply prose with inline timecode citations (07 §6.3). Text carrying `[[c1]]` tokens (EB-7) gets
 * CitationChips; text without them falls back to StreamingText, whose bare `1:05` timecodes seek.
 * Each chip carries `data-cite-frame`, which SelectToAct reads for "Show in video".
 */
export function CitedText({ text, citations, streaming = false, size = 'md', className, fps, onSeek, onAttachRange, onPreviewChange, posterAt }: CitedTextProps) {
  if (!hasCitationTokens(text)) {
    return <StreamingText text={text} streaming={streaming} onTimecode={onSeek} size={size} className={className} />;
  }
  return (
    <p
      aria-busy={streaming || undefined}
      className={cx('whitespace-pre-line text-cn-fg', size === 'sm' ? 'text-cn-label' : 'text-cn-body', className)}
    >
      {splitCited(text, citations, streaming).map((segment, index) => {
        if (segment.kind === 'text') return <span key={index}>{segment.text}</span>;
        const [first, ...rest] = segment.citations;
        const chip = toChipCitation(first, fps, posterAt?.(first.start_f));
        return (
          <span key={index} data-cite-frame={first.start_f}>
            <CitationChip
              citation={chip}
              more={rest.length}
              onSeek={onSeek}
              onAttach={onAttachRange && (() => onAttachRange(range(first)))}
              onPreviewChange={onPreviewChange && ((on) => onPreviewChange(on ? range(first) : null))}
            />
          </span>
        );
      })}
    </p>
  );
}
