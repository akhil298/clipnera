"use client";
import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Highlighter, RotateCcw, Scissors, Search, X } from 'lucide-react';
import type { TranscriptSegment, WordTimestamp } from '@/lib/types';
import { cutRanges, formatClock, isWordCut } from './studioUtils';

interface TranscriptPanelProps {
  segments: TranscriptSegment[];
  removed: ReadonlySet<number>;
  currentTime: number;
  isPlaying: boolean;
  onSeek: (time: number) => void;
  onCut: (words: WordTimestamp[], cut: boolean) => void;
  onHighlight: (words: WordTimestamp[], highlighted: boolean) => void;
  onCutFillers: () => void;
  /** Touch screens: a tap extends the selection instead of starting a new one. */
  tapToExtend?: boolean;
  showHeading?: boolean;
}

interface Selection {
  anchor: number;
  focus: number;
}

const wordClass = (state: 'cut' | 'selected' | 'now' | 'highlighted' | 'past' | 'plain'): string =>
  ({
    cut: 'line-through decoration-rose-400 text-rose-300/60 bg-rose-500/10',
    selected: 'bg-sky-400/30 text-sky-50',
    now: 'bg-neutral-100 text-neutral-950',
    highlighted: 'text-violet-300 bg-violet-400/15 font-semibold',
    past: 'text-neutral-500 hover:bg-neutral-800',
    plain: 'text-neutral-300 hover:bg-neutral-800',
  })[state];

/**
 * The clip's words, edited as text. Select words to cut or highlight them;
 * clicking a word also moves the playhead there. Cut words stay visible,
 * struck through, so they can be restored.
 */
export function TranscriptPanel({
  segments,
  removed,
  currentTime,
  isPlaying,
  onSeek,
  onCut,
  onHighlight,
  onCutFillers,
  tapToExtend = false,
  showHeading = true,
}: TranscriptPanelProps) {
  const words = useMemo(() => segments.flatMap((s) => s.words), [segments]);
  const indexById = useMemo(() => new Map(words.map((w, i) => [w.id, i])), [words]);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [query, setQuery] = useState('');
  const [matchCursor, setMatchCursor] = useState(0);
  const bodyRef = useRef<HTMLDivElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  const range = selection
    ? { lo: Math.min(selection.anchor, selection.focus), hi: Math.max(selection.anchor, selection.focus) }
    : null;
  const selectedWords = range ? words.slice(range.lo, range.hi + 1) : [];
  const allCut = selectedWords.length > 0 && selectedWords.every((w) => isWordCut(w, removed));
  const cuttable = selectedWords.some((w) => w.sourceStart !== undefined);
  const allHighlighted = selectedWords.length > 0 && selectedWords.every((w) => w.highlighted);

  const currentId = useMemo(
    () => words.find((w) => !isWordCut(w, removed) && currentTime >= w.start && currentTime < w.end)?.id,
    [words, removed, currentTime],
  );

  const needle = query.trim().toLowerCase();
  const matches = useMemo(
    () => (needle ? words.filter((w) => w.text.toLowerCase().includes(needle)) : []),
    [words, needle],
  );
  const matchIds = useMemo(() => new Set(matches.map((w) => w.id)), [matches]);

  const cutSummary = useMemo(() => {
    const ranges = cutRanges(words, removed);
    return { count: ranges.length, seconds: ranges.reduce((sum, r) => sum + r.end - r.start, 0) };
  }, [words, removed]);
  const highlightedCount = useMemo(() => words.filter((w) => w.highlighted).length, [words]);

  const scrollToWord = (id: string, onlyIfHidden: boolean) => {
    const body = bodyRef.current;
    const el = body?.querySelector<HTMLElement>(`[data-word="${id}"]`);
    if (!body || !el) return;
    const top = el.offsetTop;
    if (onlyIfHidden && top > body.scrollTop + 24 && top < body.scrollTop + body.clientHeight - 48) return;
    body.scrollTo({ top: Math.max(0, top - body.clientHeight / 3), behavior: 'smooth' });
  };

  // Follow the spoken word while playing.
  useEffect(() => {
    if (isPlaying && currentId) scrollToWord(currentId, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPlaying, currentId]);

  // Float the action bar above the first selected word.
  useLayoutEffect(() => {
    const body = bodyRef.current;
    const pop = popRef.current;
    if (!range || !body || !pop) return;
    const first = body.querySelector<HTMLElement>(`[data-index="${range.lo}"]`);
    if (!first) return;
    const maxLeft = body.clientWidth - pop.offsetWidth - 4;
    pop.style.left = `${Math.max(4, Math.min(maxLeft, first.offsetLeft - 8))}px`;
    const above = first.offsetTop - pop.offsetHeight - 6;
    pop.style.top = `${above >= body.scrollTop ? above : first.offsetTop + first.offsetHeight + 6}px`;
  });

  const applyCut = () => {
    if (!cuttable) return;
    onCut(selectedWords, !allCut);
    setSelection(null);
  };
  const applyHighlight = () => {
    onHighlight(selectedWords, !allHighlighted);
    setSelection(null);
  };

  // Selection shortcuts win over the Studio's own (Esc would otherwise leave the editor).
  const actionsRef = useRef({ applyCut, applyHighlight });
  actionsRef.current = { applyCut, applyHighlight };
  const hasSelection = selection !== null;
  useEffect(() => {
    if (!hasSelection) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === 'Backspace' || e.key === 'Delete') actionsRef.current.applyCut();
      else if (e.key === 'h' || e.key === 'H') actionsRef.current.applyHighlight();
      else if (e.key === 'Escape') setSelection(null);
      else return;
      e.preventDefault();
      e.stopPropagation();
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [hasSelection]);

  useEffect(() => {
    const stop = () => {
      draggingRef.current = false;
    };
    window.addEventListener('pointerup', stop);
    return () => window.removeEventListener('pointerup', stop);
  }, []);

  const wordIndexAt = (target: EventTarget): number | null => {
    const el = (target as HTMLElement).closest<HTMLElement>('[data-index]');
    return el ? Number(el.dataset.index) : null;
  };

  const onPointerDown = (e: React.PointerEvent) => {
    if (popRef.current?.contains(e.target as Node)) return;
    const index = wordIndexAt(e.target);
    if (index === null) {
      setSelection(null);
      return;
    }
    if (range && (e.shiftKey || (tapToExtend && e.pointerType !== 'mouse'))) {
      if (tapToExtend && index >= range.lo && index <= range.hi) setSelection(null);
      else setSelection({ anchor: selection!.anchor, focus: index });
      return;
    }
    setSelection({ anchor: index, focus: index });
    draggingRef.current = e.pointerType === 'mouse';
    onSeek(words[index].start + 0.01);
  };

  const onPointerOver = (e: React.PointerEvent) => {
    if (!draggingRef.current || !selection) return;
    const index = wordIndexAt(e.target);
    if (index !== null && index !== selection.focus) setSelection({ anchor: selection.anchor, focus: index });
  };

  const jumpToMatch = (step: number) => {
    if (!matches.length) return;
    const next = (matchCursor + step + matches.length) % matches.length;
    setMatchCursor(next);
    onSeek(matches[next].start + 0.01);
    scrollToWord(matches[next].id, false);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 px-3.5 pt-3 pb-2.5">
        {showHeading ? (
          <h2 className="flex-1 text-[13px] font-bold text-white">Transcript</h2>
        ) : (
          <span className="flex-1 text-[11.5px] text-neutral-500">Tap a word, then tap another to select a range</span>
        )}
        <button
          type="button"
          onClick={onCutFillers}
          className="h-7 px-2.5 shrink-0 rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20 text-[11.5px] font-semibold inline-flex items-center gap-1.5"
          title="Cut every um, uh and like"
        >
          <Scissors className="w-3.5 h-3.5" aria-hidden />
          Cut fillers
        </button>
      </div>
      <label className="mx-3.5 mb-2 h-8 flex items-center gap-2 px-2.5 rounded-[9px] border border-neutral-800 bg-neutral-900 text-neutral-500 focus-within:border-neutral-600">
        <Search className="w-3.5 h-3.5 shrink-0" aria-hidden />
        <input
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setMatchCursor(-1);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              jumpToMatch(e.shiftKey ? -1 : 1);
            } else if (e.key === 'Escape') {
              e.stopPropagation();
              setQuery('');
              (e.target as HTMLInputElement).blur();
            }
          }}
          placeholder="Search the transcript"
          aria-label="Search the transcript"
          className="min-w-0 flex-1 bg-transparent text-xs text-neutral-100 placeholder:text-neutral-500 outline-none"
        />
        {needle && (
          <span className="text-[11px] tabular-nums text-neutral-400 whitespace-nowrap">
            {matches.length ? `${Math.max(0, matchCursor) + 1}/${matches.length}` : 'No match'}
          </span>
        )}
      </label>

      <div
        ref={bodyRef}
        onPointerDown={onPointerDown}
        onPointerOver={onPointerOver}
        className="relative flex-1 min-h-0 overflow-y-auto px-3.5 pt-1 pb-3 space-y-3.5 select-none"
      >
        {words.length === 0 && (
          <p className="pt-6 text-center text-xs text-neutral-500">No transcript yet for this clip.</p>
        )}
        {segments.map((segment) =>
          segment.words.length ? (
            <div key={segment.id} className="grid grid-cols-[38px_minmax(0,1fr)] gap-1.5">
              <span className="pt-[3px] font-mono text-[11px] text-neutral-500 tabular-nums">{formatClock(segment.start)}</span>
              <p className="text-sm leading-[1.75]">
                {segment.words.map((word) => {
                  const index = indexById.get(word.id)!;
                  const state = isWordCut(word, removed)
                    ? 'cut'
                    : range && index >= range.lo && index <= range.hi
                    ? 'selected'
                    : word.id === currentId
                    ? 'now'
                    : word.highlighted
                    ? 'highlighted'
                    : word.end <= currentTime
                    ? 'past'
                    : 'plain';
                  return (
                    <React.Fragment key={word.id}>
                      <span
                        data-index={index}
                        data-word={word.id}
                        className={`cursor-pointer rounded px-px ${wordClass(state)} ${
                          matchIds.has(word.id) ? 'ring-1 ring-amber-400/70' : ''
                        }`}
                      >
                        {word.text}
                      </span>{' '}
                    </React.Fragment>
                  );
                })}
              </p>
            </div>
          ) : null,
        )}

        {range && (
          <div
            ref={popRef}
            role="toolbar"
            aria-label="Selected words"
            className="absolute z-10 flex gap-0.5 p-1 rounded-[11px] border border-neutral-700 bg-neutral-800 shadow-xl shadow-black/60"
          >
            <button
              type="button"
              onClick={applyCut}
              disabled={!cuttable}
              title={cuttable ? undefined : 'These words have no timing, so they cannot be cut'}
              className="h-7 px-2.5 rounded-lg inline-flex items-center gap-1.5 text-xs font-semibold text-white hover:bg-neutral-700 disabled:opacity-40"
            >
              {allCut ? <RotateCcw className="w-3.5 h-3.5" aria-hidden /> : <Scissors className="w-3.5 h-3.5" aria-hidden />}
              {allCut ? 'Restore' : 'Cut'}
              <kbd className="font-mono text-[10px] text-neutral-500">⌫</kbd>
            </button>
            <button
              type="button"
              onClick={applyHighlight}
              className="h-7 px-2.5 rounded-lg inline-flex items-center gap-1.5 text-xs font-semibold text-white hover:bg-neutral-700"
            >
              <Highlighter className="w-3.5 h-3.5" aria-hidden />
              {allHighlighted ? 'Unhighlight' : 'Highlight'}
              <kbd className="font-mono text-[10px] text-neutral-500">H</kbd>
            </button>
            <button
              type="button"
              onClick={() => setSelection(null)}
              aria-label="Clear selection"
              className="h-7 w-7 rounded-lg inline-flex items-center justify-center text-neutral-400 hover:bg-neutral-700 hover:text-white"
            >
              <X className="w-3.5 h-3.5" aria-hidden />
            </button>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-1 border-t border-neutral-800 px-3.5 py-2.5 text-[11.5px] text-neutral-400">
        <span>
          <i className="inline-block w-[7px] h-[7px] rounded-sm bg-rose-400 mr-1 align-[1px]" aria-hidden />
          <b className="text-white">{cutSummary.count} cut</b> · {cutSummary.seconds.toFixed(1)} s removed
        </span>
        <span>
          <i className="inline-block w-[7px] h-[7px] rounded-sm bg-violet-400 mr-1 align-[1px]" aria-hidden />
          <b className="text-white">{highlightedCount} words</b> highlighted
        </span>
        {!tapToExtend && <span className="text-neutral-500">Drag or shift-click to select</span>}
      </div>
    </div>
  );
}
