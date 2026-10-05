'use client';

import { Fragment, type ReactNode } from 'react';

import { completedSentences, type MdInline, parseMarkdownLite } from '@/lib/design/markdownLite';
import { cx, focusRing } from '@/lib/design/styles';
import { parseTimecode, spokenDuration } from '@/lib/design/timecode';
import { useReducedMotion } from '@/lib/design/useReducedMotion';

import { CitationMarker } from './SourceCard';

export interface StreamingTextProps {
  /** The reply so far. Re-render with the longer text as deltas arrive. */
  text: string;
  /** More is coming: new word groups fade in (120 ms); the block is `aria-busy`. */
  streaming?: boolean;
  /** Turns `1:05` into a button that seeks the preview. Without it, timecodes are plain mono text. */
  onTimecode?: (seconds: number) => void;
  /** Turns `[2]` into a citation button for SourceCard 2. Without it, `[2]` stays text. */
  onCitation?: (index: number) => void;
  /** `sm` for dense panels. */
  size?: 'sm' | 'md';
  className?: string;
}

const FADE = 'motion-safe:animate-in motion-safe:fade-in motion-safe:duration-cn-stream';

/** Splits text into word groups that each fade in once, on mount; earlier groups keep their nodes. */
function Words({ text, animate, keyPrefix }: { text: string; animate: boolean; keyPrefix: string }) {
  if (!animate) return <>{text}</>;
  const groups = text.match(/\s*\S+(?:\s+\S+){0,2}\s*/g) ?? [text];
  return (
    <>
      {groups.map((group, index) => (
        <span key={`${keyPrefix}-${index}`} className={FADE}>
          {group}
        </span>
      ))}
    </>
  );
}

function Inline({ inline, animate, keyPrefix, onTimecode, onCitation }: { inline: MdInline; animate: boolean; keyPrefix: string } & Pick<StreamingTextProps, 'onTimecode' | 'onCitation'>): ReactNode {
  switch (inline.type) {
    case 'text':
      return <Words text={inline.text} animate={animate} keyPrefix={keyPrefix} />;
    case 'strong':
      return (
        <strong className="font-semibold text-cn-fg">
          <Words text={inline.text} animate={animate} keyPrefix={keyPrefix} />
        </strong>
      );
    case 'em':
      return (
        <em>
          <Words text={inline.text} animate={animate} keyPrefix={keyPrefix} />
        </em>
      );
    case 'code':
      return <code className="rounded-cn-xs bg-cn-surface-active px-1 font-cn-mono text-cn-label text-cn-fg">{inline.text}</code>;
    case 'link':
      return (
        <a href={inline.href} target="_blank" rel="noopener noreferrer" className={cx('rounded-cn-xs text-cn-accent-text underline underline-offset-2 hover:no-underline', focusRing)}>
          {inline.text}
        </a>
      );
    case 'citation':
      return onCitation ? <CitationMarker index={inline.index} onClick={() => onCitation(inline.index)} /> : `[${inline.index}]`;
    case 'timecode': {
      const seconds = parseTimecode(inline.text);
      if (seconds === null || !onTimecode) return <span className="font-cn-mono tabular-nums text-cn-fg">{inline.text}</span>;
      return (
        <button
          type="button"
          onClick={() => onTimecode(seconds)}
          aria-label={`Play from ${spokenDuration(seconds)}`}
          className={cx(
            'rounded-cn-xs bg-cn-accent-subtle px-1 font-cn-mono tabular-nums text-cn-accent-text transition-colors duration-cn-fast hover:bg-cn-accent/20 active:bg-cn-accent/30',
            focusRing,
          )}
        >
          {inline.text}
        </button>
      );
    }
  }
}

/**
 * An agent reply: Markdown-lite (paragraphs, headings, lists, code, bold,
 * italic, safe links) with optional timecode and citation buttons. While
 * streaming, word groups fade in over 120 ms with no caret; under reduced
 * motion only finished sentences show, so it arrives sentence by sentence
 * (01 §10). Announcing the finished reply is the conversation's job.
 */
export function StreamingText({ text, streaming = false, onTimecode, onCitation, size = 'md', className }: StreamingTextProps) {
  const reduced = useReducedMotion();
  const visible = streaming && reduced ? completedSentences(text) : text;
  const animate = streaming && !reduced;
  const blocks = parseMarkdownLite(visible);
  const handlers = { onTimecode, onCitation };

  const inlines = (items: MdInline[], prefix: string) =>
    items.map((inline, index) => (
      <Fragment key={`${prefix}-${index}`}>
        <Inline inline={inline} animate={animate} keyPrefix={`${prefix}-${index}`} {...handlers} />
      </Fragment>
    ));

  return (
    <div
      aria-busy={streaming || undefined}
      className={cx('flex flex-col gap-3 text-cn-fg-secondary', size === 'sm' ? 'text-cn-label' : 'text-cn-body', className)}
    >
      {blocks.map((block, index) => {
        const key = `b${index}`;
        switch (block.type) {
          case 'heading':
            return (
              <p key={key} className="font-semibold text-cn-fg">
                {inlines(block.inlines, key)}
              </p>
            );
          case 'list': {
            const List = block.ordered ? 'ol' : 'ul';
            return (
              <List key={key} className={cx('space-y-1 pl-5 marker:text-cn-fg-muted', block.ordered ? 'list-decimal' : 'list-disc')}>
                {block.items.map((item, itemIndex) => (
                  <li key={`${key}-${itemIndex}`}>{inlines(item, `${key}-${itemIndex}`)}</li>
                ))}
              </List>
            );
          }
          case 'code':
            return (
              <pre key={key} className="overflow-x-auto rounded-cn-md border border-cn-border bg-cn-field p-3 font-cn-mono text-cn-label text-cn-fg">
                <code>{block.text}</code>
              </pre>
            );
          default:
            return <p key={key}>{inlines(block.inlines, key)}</p>;
        }
      })}
    </div>
  );
}
