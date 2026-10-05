'use client';

import { Download, Trash2, X } from 'lucide-react';

import { Button } from '@/components/ui';

import { canDownload, type ProjectActions } from './ProjectMenu';
import { plural, type ProjectView } from './projectState';

/** Floating bulk toolbar while projects are selected (07 §5.5, DS-13). */
export function SelectionBar({
  selected,
  actions,
  downloading,
  onClear,
}: {
  selected: readonly ProjectView[];
  actions: ProjectActions;
  downloading: boolean;
  onClear: () => void;
}) {
  const downloadable = selected.filter(canDownload);
  const nothingToDownload = downloadable.length === 0;

  return (
    <div
      role="region"
      aria-label="Selected projects"
      className="sticky bottom-4 z-cn-raised mx-auto flex w-full max-w-xl flex-wrap items-center gap-2 rounded-cn-xl border border-cn-border-strong bg-cn-surface-raised p-2 shadow-cn-2 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 motion-safe:duration-cn-base"
    >
      <span aria-live="polite" className="px-2 text-cn-label font-semibold text-cn-fg">
        {selected.length} selected
      </span>
      <span className="flex-1" />
      <Button
        size="sm"
        variant="secondary"
        leadingIcon={<Download />}
        disabled={!actions.online || nothingToDownload}
        loading={downloading}
        loadingLabel="Packing clips"
        onClick={() => actions.download(downloadable)}
      >
        {downloadable.length > 0 && downloadable.length < selected.length
          ? `Download clips (${plural(downloadable.length, 'project')})`
          : 'Download clips'}
      </Button>
      <Button size="sm" variant="ghost" leadingIcon={<Trash2 />} disabled={!actions.online} onClick={() => actions.remove(selected)}>
        Delete
      </Button>
      <Button size="sm" variant="ghost" leadingIcon={<X />} onClick={onClear} aria-keyshortcuts="Escape">
        Clear
      </Button>
      {nothingToDownload && actions.online && (
        <p className="w-full px-2 pb-1 text-cn-caption text-cn-fg-secondary">None of these has finished clips to download yet.</p>
      )}
    </div>
  );
}
