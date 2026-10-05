import type { ProjectClip } from '@/lib/api/clips';

/** Pure helpers that turn a clip into a moment card: its quote, format tag, place in the source. */

const QUOTE_MAX_WORDS = 24;
const SENTENCE_END = /[.?!…]["”’)]?$/;

/**
 * The words the moment opens with, as spoken: the first sentence of the clip's
 * own captions (the hook teaser comes first when there is one). Falls back to
 * the written headline when a clip has no captions yet.
 */
export function quoteOf(clip: ProjectClip): { text: string; spoken: boolean } {
  const words: string[] = [];
  for (const word of clip.captions ?? []) {
    const text = word.text?.trim();
    if (!text) continue;
    words.push(text);
    if (SENTENCE_END.test(text) && words.length >= 4) break;
    if (words.length >= QUOTE_MAX_WORDS) {
      words.push('…');
      break;
    }
  }
  if (words.length > 0) return { text: words.join(' ').replace(/ …$/, '…'), spoken: true };
  return { text: (clip.description || clip.title || 'Untitled moment').trim(), spoken: false };
}

/** `talking_head` → "Talking head". The AI-picked format when the clip has one, else its content category. */
export function formatTagOf(clip: ProjectClip): string | null {
  const raw = clip.analysis_json?.clip?.content_format || clip.content_category;
  if (!raw || raw === 'unknown') return null;
  const words = raw.replace(/[_-]+/g, ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export const durationOf = (clip: ProjectClip): number =>
  Math.max(0, clip.duration_seconds ?? clip.end_time - clip.start_time);

/** A clip can be played and downloaded once its cut reached storage. */
export const isPlayable = (clip: ProjectClip): boolean => Boolean(clip.presigned_url) && clip.status !== 'failed';

export type ClipSort = 'score' | 'order' | 'length';

export const SORTS: ReadonlyArray<{ value: ClipSort; label: string }> = [
  { value: 'score', label: 'Best first' },
  { value: 'order', label: 'Video order' },
  { value: 'length', label: 'Longest' },
];

/** Score floors, as in the old clip view. */
export const SCORE_FLOORS = [
  { value: 0, label: 'All scores' },
  { value: 70, label: '70 and up' },
  { value: 85, label: '85 and up' },
  { value: 90, label: '90 and up' },
] as const;

export function arrangeClips(clips: readonly ProjectClip[], sort: ClipSort, floor: number, format: string | null): ProjectClip[] {
  const kept = clips.filter((clip) => (clip.score ?? 0) >= floor && (format === null || formatTagOf(clip) === format));
  const by: Record<ClipSort, (a: ProjectClip, b: ProjectClip) => number> = {
    score: (a, b) => (b.score ?? -1) - (a.score ?? -1),
    order: (a, b) => a.start_time - b.start_time,
    length: (a, b) => durationOf(b) - durationOf(a),
  };
  return [...kept].sort(by[sort]);
}

/** Rank by score across the whole project, so "#1" means the same thing under any sort. */
export function ranksOf(clips: readonly ProjectClip[]): Map<string, number> {
  const ordered = [...clips].sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
  return new Map(ordered.map((clip, index) => [clip.id, index + 1]));
}
