/**
 * Pure helpers for the conversation cards: `[[c1]]` citation tokens (EB-7), frames → seconds for
 * CitationChip and SourceStrip, and the counted result summary. Type-only imports, so `node --test`
 * runs it directly (citations.test.mts).
 */
import type { Citation as ChipCitation } from '@/components/ui/CitationChip';
import type { Moment } from '@/components/ui/SourceStrip';
import type { Citation, FindingItem, RunEventOf } from '@/lib/api/editor/types';

export type CitedSegment = { kind: 'text'; text: string } | { kind: 'cite'; citations: Citation[] };

/** A span of the timeline in whole frames, like the selection store's `range`. */
export interface FrameRange {
  start: number;
  end: number;
}

const TOKEN = /\[\[([\w-]+)\]\]/g;
/** An unfinished token at the end of streamed text: `[`, `[[c`, `[[c1]`. */
const PARTIAL_TOKEN = /\[(?:\[[\w-]*\]?)?$/;
const SENTENCE_END = /[.!?](?:\s|$)/g;
/** Three or more citations in one sentence collapse to one chip with "+N" (07 §6.3). */
const COLLAPSE_AT = 3;

export const hasCitationTokens = (text: string): boolean => /\[\[[\w-]+\]\]/.test(text);

/**
 * Splits reply text into prose and citation chips. Unknown ids are dropped; while streaming, a
 * half-written token at the end is held back.
 */
export function splitCited(text: string, citations: ReadonlyArray<Citation>, streaming = false): CitedSegment[] {
  const byId = new Map(citations.map((citation) => [citation.id, citation]));
  const source = streaming ? text.replace(PARTIAL_TOKEN, '') : text;
  const segments: CitedSegment[] = [];
  const sentenceOf: number[] = [];
  let sentence = 0;
  let last = 0;
  const pushText = (chunk: string) => {
    if (!chunk) return;
    segments.push({ kind: 'text', text: chunk });
    sentence += chunk.match(SENTENCE_END)?.length ?? 0;
  };
  for (const match of source.matchAll(TOKEN)) {
    pushText(source.slice(last, match.index));
    last = (match.index ?? 0) + match[0].length;
    const citation = byId.get(match[1]);
    if (!citation) continue;
    sentenceOf[segments.length] = sentence;
    segments.push({ kind: 'cite', citations: [citation] });
  }
  pushText(source.slice(last));
  return collapse(segments, sentenceOf);
}

function collapse(segments: CitedSegment[], sentenceOf: number[]): CitedSegment[] {
  const groups = new Map<number, number[]>();
  segments.forEach((segment, index) => {
    if (segment.kind !== 'cite') return;
    const key = sentenceOf[index];
    groups.set(key, [...(groups.get(key) ?? []), index]);
  });
  const drop = new Set<number>();
  const merged = new Map<number, Citation[]>();
  for (const indexes of groups.values()) {
    if (indexes.length < COLLAPSE_AT) continue;
    merged.set(indexes[0], indexes.flatMap((index) => (segments[index] as { citations: Citation[] }).citations));
    indexes.slice(1).forEach((index) => drop.add(index));
  }
  return segments.flatMap((segment, index) => {
    if (drop.has(index)) return [];
    const group = merged.get(index);
    return group ? [{ kind: 'cite' as const, citations: group }] : [segment];
  });
}

/** The CitationChip shape (seconds) for a wire citation (frames). A zero-length span is a point. */
export function toChipCitation(citation: Citation, fps: number, thumbnail?: string): ChipCitation {
  const start = citation.start_f / fps;
  return {
    start,
    end: citation.end_f > citation.start_f ? citation.end_f / fps : undefined,
    quote: citation.text || undefined,
    thumbnail,
  };
}

/** Finding labels arrive quoted ("“a coffee a day”"); the strip adds its own curly quotes. */
const unquote = (text: string) => text.replace(/^["“]+|["”]+$/g, '');

export function momentFromFinding(item: FindingItem, fps: number, pending = false): Moment {
  return {
    id: item.id,
    quote: unquote(item.label),
    start: item.start_f / fps,
    duration: item.end_f > item.start_f ? (item.end_f - item.start_f) / fps : undefined,
    tag: item.tag,
    score: item.score,
    poster: item.poster_url,
    pending,
  };
}

/** A citation as a source-strip card, so a reply citing 2+ moments gets a strip too. */
export const findingFromCitation = (citation: Citation): FindingItem => ({
  id: citation.id,
  start_f: citation.start_f,
  end_f: citation.end_f,
  label: citation.text,
});

/**
 * The cards above a reply: the run's findings when it streamed any (EB-8), otherwise the moments the
 * reply cites, but only when it cites two or more (07 §6.3). One card per start frame.
 */
export function replySources(findings: ReadonlyArray<FindingItem>, citations: ReadonlyArray<Citation>): FindingItem[] {
  if (findings.length > 0) return [...findings];
  const byStart = new Map<number, Citation>();
  for (const citation of citations) if (!byStart.has(citation.start_f)) byStart.set(citation.start_f, citation);
  return byStart.size >= 2 ? Array.from(byStart.values(), findingFromCitation) : [];
}

export type RunResult = RunEventOf<'run.result'>['data'];

export interface ResultSummary {
  status: 'done' | 'partial' | 'stopped';
  /** Leads with counts: "2 of 3 done." */
  summary: string;
  /** Shown as a list under the summary when the summary itself does not carry them. */
  changes: string[];
}

const sentence = (text: string) => (/[.!?]$/.test(text) ? text : `${text}.`);

/** The counted summary line of a result (07 §6.2 rule 5). Real numbers only: everything comes from the event. */
export function summariseResult(result: RunResult, stopped: boolean): ResultSummary {
  const { done, not_done: notDone } = result.summary;
  const total = done.length + notDone.length;
  if (stopped) return { status: 'stopped', summary: `Stopped · ${done.length} of ${total} done.`, changes: done };
  if (done.length === 0 && notDone.length > 0) {
    return { status: 'partial', summary: sentence(`Nothing changed: ${notDone[0].reason}`), changes: [] };
  }
  if (result.status === 'partial') return { status: 'partial', summary: `${done.length} of ${total} done.`, changes: done };
  return { status: 'done', summary: sentence(done.join(' · ') || 'Done'), changes: [] };
}

/** "0:42" from two epoch-ms times; null when the start is unknown. */
export function elapsedSeconds(startedAt: number | undefined, endedAt: number | undefined, now: number): number | null {
  if (startedAt === undefined) return null;
  return Math.max(0, ((endedAt ?? now) - startedAt) / 1000);
}

/** "2nd", "3rd", "11th". */
export function ordinal(n: number): string {
  const tens = n % 100;
  if (tens >= 11 && tens <= 13) return `${n}th`;
  return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th'}`;
}

/** The first moment named in a piece of selected text: a citation the selection crosses, else a bare timecode. */
export function firstTimecodeIn(text: string): string | null {
  return /(?:\d{1,2}:)?\d{1,2}:\d{2}/.exec(text)?.[0] ?? null;
}
