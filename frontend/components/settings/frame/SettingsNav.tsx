'use client';

import { ChevronRight, SearchX } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useId, useMemo, useState } from 'react';

import { SearchField } from '@/components/ui';
import { cx, focusRing } from '@/lib/design/styles';

import { searchSettings, SETTINGS_SEARCH_ENTRIES } from './search';
import type { SettingsSection, SettingsSectionId } from './sections';

interface SettingsNavProps {
  sections: readonly SettingsSection[];
  /** The section on screen; none on the phone list. */
  currentId: SettingsSectionId | null;
  /** `rail`: the 224 px desktop column. `list`: the phone page, one 56 px row per section with its description. */
  variant: 'rail' | 'list';
}

/** Search settings, then the sections (or what the search found). Links change the URL, so this is navigation, not tabs. */
export function SettingsNav({ sections, currentId, variant }: SettingsNavProps) {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const resultsId = useId();
  const visible = useMemo(() => new Set(sections.map((item) => item.id)), [sections]);
  const results = useMemo(
    () => searchSettings(query, SETTINGS_SEARCH_ENTRIES.filter((entry) => !entry.section || visible.has(entry.section))),
    [query, visible],
  );
  const searching = query.trim().length > 0;
  const list = variant === 'list';

  const go = (href: string) => {
    setQuery('');
    router.push(href);
  };

  return (
    <nav aria-label="Settings sections" className="space-y-3">
      <SearchField
        value={query}
        onValueChange={setQuery}
        aria-label="Search settings"
        placeholder="Search settings"
        aria-controls={searching ? resultsId : undefined}
        size={list ? 'lg' : 'md'}
        onSearch={() => results[0] && go(results[0].href)}
      />

      {searching ? (
        <div id={resultsId}>
          <p role="status" className="sr-only">
            {results.length === 0 ? 'No settings match' : `${results.length} ${results.length === 1 ? 'setting matches' : 'settings match'}`}
          </p>
          {results.length === 0 ? (
            <div className="flex flex-col items-start gap-1 rounded-cn-lg border border-dashed border-cn-border p-4">
              <SearchX aria-hidden className="size-4 text-cn-fg-muted" />
              <p className="text-cn-label font-semibold text-cn-fg">Nothing in settings matches “{query.trim()}”</p>
              <p className="text-cn-caption text-cn-fg-secondary">Try a word like plan, email, team, YouTube or delete.</p>
            </div>
          ) : (
            <ul className="space-y-0.5">
              {results.map((entry) => (
                <li key={entry.id}>
                  <Link
                    href={entry.href}
                    onClick={() => setQuery('')}
                    className={cx(
                      'flex min-h-11 flex-col justify-center rounded-cn-md px-3 py-1.5 hover:bg-cn-surface-hover active:bg-cn-surface-active',
                      focusRing,
                    )}
                  >
                    <span className="text-cn-body font-medium text-cn-fg">{entry.label}</span>
                    <span className="text-cn-caption text-cn-fg-muted">{entry.context}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <ul className={list ? 'divide-y divide-cn-border overflow-hidden rounded-cn-lg border border-cn-border bg-cn-surface' : 'space-y-0.5'}>
          {sections.map((item) => {
            const current = item.id === currentId;
            return (
              <li key={item.id}>
                <Link
                  href={item.href}
                  aria-current={current ? 'page' : undefined}
                  className={cx(
                    'flex items-center gap-3 transition-colors duration-cn-fast [&_svg]:size-4 [&_svg]:shrink-0',
                    list
                      ? 'min-h-14 px-4 py-2 hover:bg-cn-surface-hover active:bg-cn-surface-active'
                      : 'h-9 rounded-cn-md px-3 text-cn-body',
                    !list && (current ? 'bg-cn-surface-active font-semibold text-cn-fg' : 'text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg active:bg-cn-surface-active'),
                    focusRing,
                  )}
                >
                  <span aria-hidden className={current ? 'text-cn-accent-text' : list ? 'text-cn-fg-secondary' : undefined}>
                    {item.icon}
                  </span>
                  {list ? (
                    <>
                      <span className="min-w-0 flex-1">
                        <span className="block text-cn-body font-semibold text-cn-fg">{item.label}</span>
                        <span className="block text-cn-caption text-cn-fg-secondary">{item.description}</span>
                      </span>
                      <ChevronRight aria-hidden className="text-cn-fg-muted" />
                    </>
                  ) : (
                    <span className="truncate">{item.label}</span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </nav>
  );
}
