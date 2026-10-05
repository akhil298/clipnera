'use client';

import { FileText, Film, Globe, Image as ImageIcon } from 'lucide-react';
import { type ReactNode, useState } from 'react';

import { cx, focusRing, focusWithinRing } from '@/lib/design/styles';

import { cardLinkOverlay } from './Card';

export type SourceKind = 'clip' | 'broll' | 'transcript' | 'web';

const KIND: Record<SourceKind, { icon: ReactNode; noun: string }> = {
  clip: { icon: <Film />, noun: 'Clip' },
  broll: { icon: <ImageIcon />, noun: 'B-roll' },
  transcript: { icon: <FileText />, noun: 'Transcript' },
  web: { icon: <Globe />, noun: 'Web page' },
};

/** `[2]` in a reply: a small button that points at SourceCard 2. Inline text target, exempt from 2.5.8. */
export function CitationMarker({ index, onClick, className }: { index: number; onClick?: () => void; className?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Source ${index}`}
      className={cx(
        'mx-0.5 inline-flex h-4 min-w-4 -translate-y-px items-center justify-center rounded-cn-xs bg-cn-surface-active px-1 align-middle font-cn-mono text-cn-caption leading-none text-cn-fg-secondary',
        'transition-colors duration-cn-fast hover:bg-cn-accent-subtle hover:text-cn-accent-text',
        focusRing,
      )}
    >
      {index}
    </button>
  );
}

export interface Source {
  id: string;
  /** "Opening hook", "Coffee cup on a desk", "Pexels licence". */
  title: string;
  kind: SourceKind;
  /** Where it comes from: "Episode 12 · 0:42–1:10", "pexels.com". */
  origin?: string;
  /** A quoted line or why it was picked. Two lines at most. */
  snippet?: string;
  /** Small poster or favicon URL. Decorative. */
  thumbnail?: string;
  href?: string;
  onOpen?: () => void;
}

export interface SourceCardProps {
  source: Source;
  /** The citation number shown on the card and used by `[n]` in the reply. */
  index?: number;
  /** `card` is a fixed-width tile for a row; `row` is a full-width list item. */
  variant?: 'card' | 'row';
  /** Highlight after its CitationMarker is pressed. */
  highlighted?: boolean;
  className?: string;
}

/**
 * A reference behind an agent answer (Perplexity-style): the clip, B-roll shot,
 * transcript line or page it used. One link or button covers the card.
 */
export function SourceCard({ source, index, variant = 'card', highlighted = false, className }: SourceCardProps) {
  const { title, kind, origin, snippet, thumbnail, href, onOpen } = source;
  const { icon, noun } = KIND[kind];
  const name = `${index !== undefined ? `Source ${index}: ` : ''}${noun}, ${title}`;
  const target = href ? (
    <a href={href} aria-label={name} className={cx('min-w-0', cardLinkOverlay)} target={kind === 'web' ? '_blank' : undefined} rel={kind === 'web' ? 'noopener noreferrer' : undefined}>
      <span className="line-clamp-2 text-cn-label font-semibold text-cn-fg">{title}</span>
    </a>
  ) : (
    <button type="button" onClick={onOpen} aria-label={name} className={cx('min-w-0 text-left', cardLinkOverlay)}>
      <span className="line-clamp-2 text-cn-label font-semibold text-cn-fg">{title}</span>
    </button>
  );

  return (
    <div
      className={cx(
        'relative flex gap-2.5 rounded-cn-lg border bg-cn-surface p-2.5 transition-[border-color,background-color] duration-cn-fast',
        'hover:border-cn-border-strong hover:bg-cn-surface-hover active:bg-cn-surface-active',
        highlighted ? 'border-cn-accent-border' : 'border-cn-border',
        variant === 'card' ? 'w-56 shrink-0 flex-col' : 'w-full items-start',
        focusWithinRing,
        className,
      )}
    >
      <div className="flex min-w-0 items-center gap-2 text-cn-caption text-cn-fg-muted">
        {index !== undefined && (
          <span aria-hidden className="inline-flex h-5 min-w-5 items-center justify-center rounded-cn-xs bg-cn-surface-active px-1 font-cn-mono text-cn-fg-secondary">
            {index}
          </span>
        )}
        {thumbnail ? (
          <img src={thumbnail} alt="" className="size-5 shrink-0 rounded-cn-xs object-cover" />
        ) : (
          <span aria-hidden className="inline-flex shrink-0 [&_svg]:size-3.5">
            {icon}
          </span>
        )}
        {variant === 'card' && origin && <span className="min-w-0 truncate">{origin}</span>}
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        {target}
        {variant === 'row' && origin && <span className="truncate text-cn-caption text-cn-fg-muted">{origin}</span>}
        {snippet && <p className="line-clamp-2 text-cn-caption text-cn-fg-secondary">{snippet}</p>}
      </div>
    </div>
  );
}

export interface SourceListProps {
  sources: ReadonlyArray<Source>;
  /** Cards shown before "+N more". Default 4. */
  maxVisible?: number;
  label?: string;
  highlightedId?: string;
  className?: string;
}

/** The "Sources" strip above or below a reply: a horizontal row that scrolls on its own, never the page. */
export function SourceList({ sources, maxVisible = 4, label = 'Sources', highlightedId, className }: SourceListProps) {
  const [expanded, setExpanded] = useState(false);
  if (sources.length === 0) return null;
  const shown = expanded ? sources : sources.slice(0, maxVisible);
  const hidden = sources.length - shown.length;
  return (
    <section aria-label={label} className={cx('flex flex-col gap-2', className)}>
      <p className="text-cn-caption font-semibold text-cn-fg-muted">{label}</p>
      <ul className="-mx-1 flex snap-x gap-2 overflow-x-auto px-1 pb-1">
        {shown.map((source, index) => (
          <li key={source.id} className="snap-start">
            <SourceCard source={source} index={index + 1} highlighted={source.id === highlightedId} />
          </li>
        ))}
        {hidden > 0 && (
          <li className="snap-start">
            <button
              type="button"
              onClick={() => setExpanded(true)}
              className={cx(
                'flex h-full min-h-16 w-24 items-center justify-center rounded-cn-lg border border-dashed border-cn-border-strong text-cn-label font-semibold text-cn-fg-secondary',
                'transition-colors duration-cn-fast hover:bg-cn-surface-hover hover:text-cn-fg',
                focusRing,
              )}
            >
              +{hidden} more
            </button>
          </li>
        )}
      </ul>
    </section>
  );
}
