'use client';

import { SourceStrip } from '@/components/ui';
import type { Citation, FindingItem } from '@/lib/api/editor/types';

import { momentFromFinding, replySources } from './citations';

export interface ReplySourcesProps {
  /** The turn's `sources` (run.finding, EB-8). */
  findings: ReadonlyArray<FindingItem>;
  /** The turn's `citations` (EB-7); used when there are no findings and the reply cites 2+ moments. */
  citations: ReadonlyArray<Citation>;
  fps: number;
  onSeek: (seconds: number) => void;
  /** "Use this": attach the moment as a Moment chip. */
  onUseMoment?: (moment: FindingItem) => void;
  /** Findings still streaming in: cards show the pending sheen. */
  streaming?: boolean;
  posterAt?: (frame: number) => string | undefined;
  className?: string;
}

/** The moment strip above a reply (07 §6.3–6.4): up to 4 cards plus "+N", scrolling sideways on phones. */
export function ReplySources({ findings, citations, fps, onSeek, onUseMoment, streaming = false, posterAt, className }: ReplySourcesProps) {
  const items = replySources(findings, citations);
  if (items.length === 0) return null;
  const byId = new Map(items.map((item) => [item.id, item]));
  const moments = items.map((item) => momentFromFinding({ ...item, poster_url: item.poster_url ?? posterAt?.(item.start_f) }, fps, streaming));
  return (
    <SourceStrip
      label={findings.length ? `${items.length} moments found` : `${items.length} moments cited`}
      moments={moments}
      onSeek={(moment) => onSeek(moment.start)}
      onUse={onUseMoment && ((moment) => onUseMoment(byId.get(moment.id) ?? items[0]))}
      className={className}
    />
  );
}
