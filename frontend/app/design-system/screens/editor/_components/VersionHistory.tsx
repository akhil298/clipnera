'use client';

import { useState } from 'react';

import { SegmentedControl, VersionItem } from '@/components/ui';

import type { VersionRow } from './sample';

/** The history list with its All / Bookmarked filter and the stated limits (01 §7). */
export function VersionHistoryList({
  versions,
  viewingId,
  restoringId,
  onView,
  onRestore,
  onToggleBookmark,
  onRename,
}: {
  versions: ReadonlyArray<VersionRow>;
  viewingId: string | null;
  restoringId: string | null;
  onView: (id: string) => void;
  onRestore: (id: string) => void;
  onToggleBookmark: (id: string) => void;
  onRename: (id: string, name: string) => void;
}) {
  const [filter, setFilter] = useState<'all' | 'bookmarked'>('all');
  const shown = filter === 'all' ? versions : versions.filter((version) => version.bookmarked);
  return (
    <div className="flex flex-col gap-3">
      <SegmentedControl
        label="Show"
        size="sm"
        value={filter}
        onValueChange={setFilter}
        options={[
          { value: 'all', label: `All · ${versions.length}` },
          { value: 'bookmarked', label: `Bookmarked · ${versions.filter((version) => version.bookmarked).length}` },
        ]}
      />
      {shown.length === 0 ? (
        <p className="text-cn-label text-cn-fg-muted">No bookmarks yet. Bookmark a version before a big change to find it fast.</p>
      ) : (
        <ol aria-label="Versions, newest first" className="flex flex-col gap-1">
          {shown.map((version) => (
            <VersionItem
              key={version.id}
              version={{ ...version, exactTime: version.exact, restored: version.kind === 'restore' }}
              onCompare={() => onView(version.id)}
              viewing={viewingId === version.id}
              restoring={restoringId === version.id}
              onView={() => onView(version.id)}
              onRestore={() => onRestore(version.id)}
              onToggleBookmark={() => onToggleBookmark(version.id)}
              onRename={(name) => onRename(version.id, name)}
            />
          ))}
        </ol>
      )}
      <p className="text-cn-caption text-cn-fg-muted">Restoring doesn’t unpublish posted clips or return credits. Nothing is deleted: later versions stay here.</p>
    </div>
  );
}
