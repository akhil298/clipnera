'use client';

import { ChevronDown, Folder } from 'lucide-react';
import { useId } from 'react';

import { Menu, type MenuEntry } from '@/components/ui';
import type { ProjectFolder } from '@/lib/api/projects';
import { cx, focusRing } from '@/lib/design/styles';

/** Folder picker as a Menu button (Select isn't rebuilt yet, 02 §3.5). */
export function FolderField({ folders, value, onChange }: { folders: ProjectFolder[]; value: string | null; onChange: (id: string | null) => void }) {
  const labelId = useId();
  const current = folders.find((folder) => folder.id === value)?.name ?? 'No folder';
  const items: MenuEntry[] = [
    { id: 'none', label: 'No folder', checked: value === null, onSelect: () => onChange(null) },
    ...(folders.length > 0 ? [{ type: 'separator' as const, id: 'sep' }] : []),
    ...folders.map((folder) => ({ id: folder.id, label: folder.name, checked: folder.id === value, onSelect: () => onChange(folder.id) })),
  ];

  return (
    <div className="flex flex-col gap-1.5">
      <span id={labelId} className="text-cn-label font-semibold text-cn-fg">
        Folder
      </span>
      <Menu
        items={items}
        trigger={(props) => (
          <button
            type="button"
            {...props}
            aria-labelledby={`${labelId} ${props.id}`}
            className={cx(
              'flex h-9 items-center gap-2 rounded-cn-md border border-cn-control-border bg-cn-field px-3 text-left text-cn-body text-cn-fg hover:border-cn-fg-muted',
              focusRing,
            )}
          >
            <Folder aria-hidden className="size-4 text-cn-fg-muted" />
            <span className="flex-1 truncate">{current}</span>
            <ChevronDown aria-hidden className="size-4 text-cn-fg-muted" />
          </button>
        )}
      />
    </div>
  );
}
