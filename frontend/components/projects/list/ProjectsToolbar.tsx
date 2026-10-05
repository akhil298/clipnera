'use client';

import { ArrowUpDown, LayoutGrid, List } from 'lucide-react';
import { useEffect, useRef } from 'react';

import { Button, Chip, Menu, SearchField, SegmentedControl } from '@/components/ui';

import type { FilteredProjects, ProjectFilters, SortOrder, SourceFilter, StatusFilter, ViewMode } from './filters';

const SORT_LABEL: Record<SortOrder, string> = { newest: 'Newest first', oldest: 'Oldest first', name: 'Name A–Z' };
const SOURCES: { value: SourceFilter; label: string }[] = [
  { value: 'all', label: 'All sources' },
  { value: 'youtube', label: 'YouTube' },
  { value: 'upload', label: 'Uploads' },
];
const VIEWS = [
  { value: 'grid' as const, label: <LayoutGrid aria-hidden className="size-4" />, ariaLabel: 'Grid' },
  { value: 'list' as const, label: <List aria-hidden className="size-4" />, ariaLabel: 'List' },
];

function statusOptions(counts: FilteredProjects['counts']) {
  const option = (value: StatusFilter, label: string) => ({
    value,
    label: (
      <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
        {label}
        <span className="font-cn-mono text-cn-caption tabular-nums text-cn-fg-secondary">{counts[value]}</span>
      </span>
    ),
    ariaLabel: `${label}, ${counts[value]}`,
  });
  return [option('all', 'All'), option('running', 'In progress'), option('ready', 'Ready'), option('failed', 'Failed')];
}

/** "/" focuses search unless the user is already typing somewhere. */
function useSlashToSearch() {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.key !== '/' || event.metaKey || event.ctrlKey || target?.closest('input, textarea, [contenteditable="true"]')) return;
      event.preventDefault();
      ref.current?.focus();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  return ref;
}

export function ProjectsToolbar({
  filters,
  counts,
  onChange,
}: {
  filters: ProjectFilters;
  counts: FilteredProjects['counts'];
  onChange: (next: Partial<ProjectFilters>) => void;
}) {
  const searchRef = useSlashToSearch();
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <SearchField
          ref={searchRef}
          aria-label="Search projects"
          placeholder="Search projects"
          shortcut={['/']}
          value={filters.q}
          onValueChange={(q) => onChange({ q })}
          className="w-full sm:w-72"
        />
        <div className="-mx-4 min-w-0 overflow-x-auto px-4 sm:mx-0 sm:px-0 [scrollbar-width:none]">
          <SegmentedControl label="Status" options={statusOptions(counts)} value={filters.status} onValueChange={(status) => onChange({ status })} />
        </div>
        <span className="hidden flex-1 lg:block" />
        <div className="ml-auto flex items-center gap-2 lg:ml-0">
          <Menu
            align="end"
            items={(Object.keys(SORT_LABEL) as SortOrder[]).map((sort) => ({
              id: sort,
              label: SORT_LABEL[sort],
              checked: filters.sort === sort,
              onSelect: () => onChange({ sort }),
            }))}
            trigger={(props) => (
              <Button {...props} variant="ghost" size="sm" leadingIcon={<ArrowUpDown />} aria-label={`Sort: ${SORT_LABEL[filters.sort]}`}>
                {SORT_LABEL[filters.sort]}
              </Button>
            )}
          />
          <SegmentedControl<ViewMode> label="View" size="sm" options={VIEWS} value={filters.view} onValueChange={(view) => onChange({ view })} />
        </div>
      </div>
      <div role="group" aria-label="Source" className="flex flex-wrap gap-1.5">
        {SOURCES.map((source) => (
          <Chip key={source.value} size="sm" selected={filters.source === source.value} onClick={() => onChange({ source: source.value })}>
            {source.label}
          </Chip>
        ))}
      </div>
    </div>
  );
}
