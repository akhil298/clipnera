'use client';

import { Scissors, Search } from 'lucide-react';
import { type KeyboardEvent, useRef, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Kbd } from '@/components/ui/Kbd';
import { cx } from '@/lib/design/styles';

import { clock, WORDS } from './sample';

/**
 * The studio's transcript editing, kept and made keyboard-operable (audit 05
 * A1): words are a listbox with one tab stop. Click or Enter seeks; Shift+click
 * or Shift+arrows extend a selection; ⌫ cuts, H highlights. A selection
 * becomes a Caption line chip on the prompt bar.
 */
export function TranscriptPanel({
  time,
  onSeek,
  onSelection,
}: {
  time: number;
  onSeek: (seconds: number) => void;
  onSelection: (text: string | null) => void;
}) {
  const [anchor, setAnchor] = useState<number | null>(null);
  const [focus, setFocus] = useState(0);
  const [cut, setCut] = useState<Set<number>>(new Set());
  const [highlighted, setHighlighted] = useState<Set<number>>(new Set());
  const [query, setQuery] = useState('');
  const refs = useRef<Array<HTMLSpanElement | null>>([]);
  const range = anchor === null ? null : [Math.min(anchor, focus), Math.max(anchor, focus)];
  const inRange = (index: number) => range !== null && index >= range[0] && index <= range[1];
  const current = WORDS.findIndex((word, index) => time >= word.start && time < (WORDS[index + 1]?.start ?? Infinity));
  const removed = Array.from(cut).length * 0.9;

  const report = (from: number | null, to: number) => {
    if (from === null || from === to) return onSelection(from === null ? null : `“${WORDS[to].text}”`);
    const [a, b] = [Math.min(from, to), Math.max(from, to)];
    onSelection(`“${WORDS.slice(a, b + 1).map((word) => word.text).join(' ')}”`);
  };

  const move = (index: number, extend: boolean) => {
    const next = Math.max(0, Math.min(WORDS.length - 1, index));
    setFocus(next);
    refs.current[next]?.focus();
    if (extend) {
      const from = anchor ?? focus;
      setAnchor(from);
      report(from, next);
    } else {
      setAnchor(null);
      onSelection(null);
    }
  };

  const apply = (setter: typeof setCut, set: Set<number>) => {
    if (!range) return;
    const next = new Set(set);
    const all = Array.from({ length: range[1] - range[0] + 1 }, (_, offset) => range[0] + offset);
    const every = all.every((index) => next.has(index));
    all.forEach((index) => (every ? next.delete(index) : next.add(index)));
    setter(next);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      move(focus + 1, event.shiftKey);
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      move(focus - 1, event.shiftKey);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      onSeek(WORDS[focus].start);
    } else if (event.key === 'Backspace' || event.key === 'Delete') {
      event.preventDefault();
      apply(setCut, cut);
    } else if (event.key.toLowerCase() === 'h' && !event.metaKey && !event.ctrlKey) {
      event.preventDefault();
      apply(setHighlighted, highlighted);
    }
  };

  return (
    <section aria-label="Transcript" className="flex min-h-0 flex-col">
      <div className="flex items-center gap-2 px-3 pb-2 pt-3">
        <h2 className="flex-1 text-cn-label font-semibold">Transcript</h2>
        <Button
          size="sm"
          variant="secondary"
          leadingIcon={<Scissors />}
          onClick={() => setCut(new Set([...Array.from(cut), ...WORDS.flatMap((word, index) => (word.filler ? [index] : []))]))}
        >
          Cut fillers
        </Button>
      </div>
      <label className="mx-3 mb-2 flex h-8 items-center gap-2 rounded-cn-md border border-cn-control-border bg-cn-field px-2 focus-within:outline focus-within:outline-2 focus-within:outline-cn-focus">
        <Search aria-hidden className="size-3.5 text-cn-fg-muted" />
        <span className="sr-only">Search the transcript</span>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search the transcript" className="min-w-0 flex-1 bg-transparent text-cn-label text-cn-fg placeholder:text-cn-fg-muted focus-visible:outline-none" />
      </label>
      <div
        role="listbox"
        aria-label="Transcript words"
        aria-multiselectable
        onKeyDown={onKeyDown}
        className="min-h-0 flex-1 overflow-y-auto px-3 pb-3 text-cn-body leading-7"
      >
        <span className="mr-2 font-cn-mono text-cn-caption text-cn-fg-muted">0:00</span>
        {WORDS.map((word, index) => {
          const hit = query.length > 1 && word.text.toLowerCase().includes(query.toLowerCase());
          return (
            <span key={word.id}>
              <span
                ref={(node) => {
                  refs.current[index] = node;
                }}
                role="option"
                tabIndex={index === focus ? 0 : -1}
                aria-selected={inRange(index)}
                aria-label={`${word.text}, ${clock(word.start)}${cut.has(index) ? ', cut' : ''}${highlighted.has(index) ? ', highlighted' : ''}`}
                onClick={(event) => {
                  if (event.shiftKey) {
                    const from = anchor ?? focus;
                    setAnchor(from);
                    setFocus(index);
                    report(from, index);
                  } else {
                    setAnchor(index);
                    setFocus(index);
                    report(index, index);
                    onSeek(word.start);
                  }
                }}
                className={cx(
                  'cursor-pointer rounded-cn-xs px-0.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cn-focus',
                  index === current && 'bg-cn-surface-active text-cn-fg',
                  index < current && 'text-cn-fg-secondary',
                  inRange(index) && 'bg-cn-accent-subtle text-cn-accent-text outline outline-1 outline-cn-accent-border',
                  highlighted.has(index) && 'font-semibold text-cn-accent-text underline decoration-dotted underline-offset-4',
                  cut.has(index) && 'text-cn-danger-text line-through',
                  hit && 'outline outline-1 outline-cn-accent',
                )}
              >
                {word.text}
              </span>{' '}
            </span>
          );
        })}
      </div>
      <p className="flex flex-wrap items-center gap-x-2 border-t border-cn-border px-3 py-2 text-cn-caption text-cn-fg-muted">
        <span>
          <span className="font-semibold text-cn-fg-secondary">{cut.size} cut</span> · {removed.toFixed(1)} s removed
        </span>
        <span>
          <Kbd keys={['⌫']} /> cut · <Kbd keys={['H']} /> highlight · <Kbd keys={['⇧', '→']} /> select
        </span>
      </p>
    </section>
  );
}
