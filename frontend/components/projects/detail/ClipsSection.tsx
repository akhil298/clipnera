'use client';

import { Film, ListFilter, SearchX } from 'lucide-react';
import { useMemo, useState } from 'react';

import { InlineAlert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Chip } from '@/components/ui/Chip';
import { EmptyState } from '@/components/ui/EmptyState';
import { MediaGrid } from '@/components/ui/MediaGrid';
import { Menu } from '@/components/ui/Menu';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { usePersistentState } from '@/lib/design/usePersistentState';
import type { ProjectClip } from '@/lib/api/clips';

import { arrangeClips, type ClipSort, formatTagOf, ranksOf, SCORE_FLOORS, SORTS } from './moments';
import { MomentCard } from './MomentCard';

export interface ClipsSectionProps {
  clips: readonly ProjectClip[];
  loading: boolean;
  /** The run is still making clips: new ones keep arriving. */
  streaming: boolean;
  sourceSeconds: number;
}

type Notice = { tone: 'success' | 'danger'; text: string };

/** The clip grid: sort, score floor and format filters, and one live region for card actions. */
export function ClipsSection({ clips, loading, streaming, sourceSeconds }: ClipsSectionProps) {
  const [sort, setSort] = usePersistentState<ClipSort>('cn.project.clipSort', 'score');
  const [floor, setFloor] = useState(0);
  const [format, setFormat] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  const formats = useMemo(
    () => Array.from(new Set(clips.map(formatTagOf).filter((tag): tag is string => tag !== null))).sort(),
    [clips],
  );
  const ranks = useMemo(() => ranksOf(clips), [clips]);
  const shown = arrangeClips(clips, sort, floor, format);
  const filtered = floor > 0 || format !== null;
  const floorLabel = SCORE_FLOORS.find((option) => option.value === floor)?.label ?? 'All scores';

  return (
    <section aria-labelledby="clips-heading" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="clips-heading" className="text-cn-title-sm font-semibold text-cn-fg">
          {streaming ? 'Clips so far' : 'Clips'}{' '}
          {!loading && <span className="font-cn-mono text-cn-label font-medium tabular-nums text-cn-fg-muted">{clips.length}</span>}
        </h2>
        <span className="flex-1" />
        {clips.length > 1 && (
          <>
            <SegmentedControl label="Sort clips" size="sm" value={sort} onValueChange={setSort} options={SORTS} />
            <Menu
              align="end"
              trigger={(props) => (
                <Button {...props} size="sm" variant="secondary" leadingIcon={<ListFilter />}>
                  {floorLabel}
                </Button>
              )}
              items={SCORE_FLOORS.map((option) => ({
                id: String(option.value),
                label: option.label,
                checked: floor === option.value,
                onSelect: () => setFloor(option.value),
              }))}
            />
          </>
        )}
      </div>

      {formats.length > 1 && (
        <div role="group" aria-label="Filter by format" className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
          <Chip size="sm" selected={format === null} onClick={() => setFormat(null)}>
            All formats
          </Chip>
          {formats.map((tag) => (
            <Chip key={tag} size="sm" selected={format === tag} onClick={() => setFormat(format === tag ? null : tag)}>
              {tag}
            </Chip>
          ))}
        </div>
      )}

      <div aria-live="polite">
        {notice && (
          <InlineAlert tone={notice.tone} onDismiss={() => setNotice(null)}>
            {notice.text}
          </InlineAlert>
        )}
      </div>

      <MediaGrid
        label="Clips"
        items={shown}
        getKey={(clip) => clip.id}
        loading={loading}
        skeletonCount={6}
        renderItem={(clip) => <MomentCard clip={clip} rank={ranks.get(clip.id) ?? 0} sourceSeconds={sourceSeconds} onNotice={setNotice} />}
        empty={
          filtered ? (
            <EmptyState
              size="compact"
              icon={<SearchX />}
              title="No clips match these filters"
              description={`${clips.length} clip${clips.length === 1 ? ' is' : 's are'} hidden by the score or format filter.`}
              action={
                <Button
                  variant="secondary"
                  onClick={() => {
                    setFloor(0);
                    setFormat(null);
                  }}
                >
                  Show all clips
                </Button>
              }
            />
          ) : (
            <EmptyState
              size="compact"
              icon={<Film />}
              title={streaming ? 'Your clips appear here' : 'No clips came out of this video'}
              description={
                streaming
                  ? 'Each one shows up as soon as it’s cut, before the whole run ends.'
                  : 'I didn’t find a moment strong enough to stand on its own. A longer or more talk-heavy video usually gives more.'
              }
            />
          )
        }
      />
    </section>
  );
}
