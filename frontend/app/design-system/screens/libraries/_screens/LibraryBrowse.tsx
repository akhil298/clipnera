'use client';

import { CircleAlert, Library, Sparkles } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button, buttonClasses } from '@/components/ui/Button';
import { Chip } from '@/components/ui/Chip';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton, SkeletonGroup } from '@/components/ui/Skeleton';

import { Callout } from '../_components/Additions';
import { CATEGORIES, COLLECTIONS, PLATFORM_SHOTS, type SampleShot } from '../_components/data';
import { AssetDrawer, FeaturedTile, FilterSheet, LibraryFrame, ReportDialog, SearchToolbar } from '../_components/LibraryParts';
import { AssetGrid, MediaCard, Poster, TileRow } from '../_components/Media';
import { MockFrame } from '../_components/MockFrame';
import { AppShell } from '../_components/Shells';

const STATES = [
  { id: 'browse', label: 'Browse (empty query)' },
  { id: 'search', label: 'Search results' },
  { id: 'no-results', label: 'No results' },
  { id: 'loading', label: 'Loading' },
  { id: 'error', label: 'Load failed' },
  { id: 'details', label: 'Details drawer' },
  { id: 'report', label: 'Report a problem' },
  { id: 'filters', label: 'Filters sheet (phone)' },
  { id: 'tiering', label: 'Tiering on (later)' },
  { id: 'user-off', label: 'Uploads flag off' },
  { id: 'all-off', label: 'Both flags off' },
] as const;

function GridSkeleton() {
  const ratios = ['9 / 16', '9 / 16', '16 / 9', '9 / 16', '1 / 1', '9 / 16'];
  return (
    <SkeletonGroup label="Loading footage" className="flex flex-wrap gap-2">
      {ratios.concat(ratios).map((r, i) => (
        <div key={i} className="w-36 space-y-2 p-1.5">
          <Skeleton className="w-full rounded-cn-md" style={{ aspectRatio: r }} />
          <Skeleton className="h-3 w-4/5" />
        </div>
      ))}
    </SkeletonGroup>
  );
}

function ResultsGrid({ shots, onOpen, locked }: { shots: SampleShot[]; onOpen: (s: SampleShot) => void; locked?: boolean }) {
  const [favs, setFavs] = useState<Set<string>>(new Set(shots.filter((s) => s.favourite).map((s) => s.id)));
  return (
    <AssetGrid
      label="Shots"
      items={shots}
      renderItem={(i, tabIndex) => {
        const s = shots[i];
        return (
          <MediaCard
            inGrid
            tabIndex={tabIndex}
            title={s.title}
            duration={s.duration}
            look={s.look}
            orientation={s.orientation}
            status={locked && i % 4 === 1 ? 'locked' : 'live'}
            favourite={favs.has(s.id)}
            onFavourite={() => setFavs((f) => (f.has(s.id) ? new Set([...f].filter((x) => x !== s.id)) : new Set(f).add(s.id)))}
            onOpen={() => onOpen(s)}
            menu={[
              { id: 'open', label: 'Details', onSelect: () => onOpen(s) },
              { id: 'col', label: 'Add to collection…', onSelect: () => undefined },
              { id: 'use', label: 'Use in a project…', onSelect: () => undefined },
              { id: 'sep', type: 'separator' },
              { id: 'rep', label: 'Report a problem', onSelect: () => undefined },
            ]}
          />
        );
      }}
    />
  );
}

/** `/dashboard/library` — the Clipnera library tab. */
export function LibraryBrowse() {
  return (
    <MockFrame title="Library · Clipnera library" url="/dashboard/library" flag="broll_platform_library" states={STATES}>
      {(state, setState) => <Body state={state} setState={setState} />}
    </MockFrame>
  );
}

function Body({ state, setState }: { state: string; setState: (s: string) => void }) {
  const searching = ['search', 'no-results', 'details', 'report'].includes(state);
  const [query, setQuery] = useState('');
  const shown = query || (searching ? (state === 'no-results' ? 'purple giraffe skateboarding' : 'calm morning city') : '');
  const [selected, setSelected] = useState<SampleShot>(PLATFORM_SHOTS[0]);

  if (state === 'all-off') {
    return (
      <AppShell active="library">
        <EmptyState
          className="mt-16"
          icon={<Library />}
          title="The library isn't available on your account yet"
          description="We're opening it up in stages. Your projects and any footage already in them are safe."
          action={<a href="#" className={buttonClasses()}>Back to home</a>}
        />
      </AppShell>
    );
  }

  return (
    <AppShell active="library">
      <LibraryFrame tab="clipnera" userLibrary={state !== 'user-off'}>
        <SearchToolbar query={shown} onQuery={setQuery} showSource={state !== 'user-off'} onOpenSheet={() => setState('filters')} />

        {state === 'loading' && <GridSkeleton />}

        {state === 'error' && (
          <Callout
            tone="danger"
            live="alert"
            title="The library didn't load."
            action={<Button size="sm" variant="secondary">Try again</Button>}
          >
            Your projects are safe. Check your connection and try again.
          </Callout>
        )}

        {state === 'no-results' && (
          <EmptyState
            icon={<CircleAlert />}
            title={`No shots match '${shown}'`}
            description="Try fewer words, or describe what's on screen rather than the topic."
            action={
              <div className="flex flex-wrap justify-center gap-2">
                {['skateboard trick', 'giraffe close-up', 'colourful street'].map((q) => (
                  <Chip key={q} onClick={() => setQuery(q)}>
                    {q}
                  </Chip>
                ))}
              </div>
            }
          />
        )}

        {(state === 'search' || state === 'details' || state === 'report') && (
          <section aria-labelledby="results-title" className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <h2 id="results-title" className="text-cn-body font-semibold text-cn-fg">
                48 shots
              </h2>
              <Badge icon={<Sparkles />}>Matches by meaning</Badge>
              <span className="text-cn-label text-cn-fg-muted">Some results don't contain your words but show what you described.</span>
            </div>
            <ResultsGrid shots={PLATFORM_SHOTS} onOpen={(s) => { setSelected(s); setState('details'); }} />
            <div className="flex justify-center pt-2">
              <Button variant="secondary">Show more</Button>
            </div>
          </section>
        )}

        {(state === 'browse' || state === 'filters' || state === 'tiering' || state === 'user-off') && !query && (
          <div className="space-y-8">
            {state === 'tiering' && (
              <Callout tone="neutral" title="Pro footage">
                Shots marked Pro are part of the Pro plan. You can preview them; adding one opens the plan options. (Tiering is off at launch.)
              </Callout>
            )}
            {COLLECTIONS.filter((c) => c.curated).map((c, row) => (
              <section key={c.id} aria-labelledby={`feat-${c.id}`} className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <h2 id={`feat-${c.id}`} className="text-cn-title-sm font-semibold text-cn-fg">
                    {c.name}
                  </h2>
                  <Button size="sm" variant="ghost">
                    See all {c.count}
                  </Button>
                </div>
                <TileRow label={c.name}>
                  {PLATFORM_SHOTS.slice(row * 3, row * 3 + 7).map((s) => (
                    <FeaturedTile key={s.id} shot={s} onOpen={() => { setSelected(s); setState('details'); }} />
                  ))}
                </TileRow>
              </section>
            ))}
            <section aria-labelledby="cats" className="space-y-3">
              <h2 id="cats" className="text-cn-title-sm font-semibold text-cn-fg">
                Categories
              </h2>
              <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {CATEGORIES.map((cat, i) => (
                  <li key={cat}>
                    <a href="#" className="group relative block h-20 overflow-hidden rounded-cn-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cn-focus">
                      <Poster look={PLATFORM_SHOTS[i].look} className="absolute inset-0 opacity-70 transition-opacity duration-cn-fast group-hover:opacity-90" />
                      <span className="absolute inset-0 bg-cn-overlay/40" />
                      <span data-theme="dark" className="absolute bottom-2 left-3 text-cn-body font-semibold text-cn-fg">{cat}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </section>
            <section aria-labelledby="popular" className="space-y-3">
              <h2 id="popular" className="text-cn-title-sm font-semibold text-cn-fg">
                Popular this week
              </h2>
              <ResultsGrid shots={PLATFORM_SHOTS.slice(0, 8)} onOpen={(s) => { setSelected(s); setState('details'); }} locked={state === 'tiering'} />
            </section>
          </div>
        )}
      </LibraryFrame>
      <AssetDrawer shot={selected} open={state === 'details'} onOpenChange={(o) => setState(o ? 'details' : 'search')} onReport={() => setState('report')} />
      <ReportDialog open={state === 'report'} onOpenChange={(o) => setState(o ? 'report' : 'search')} />
      <FilterSheet open={state === 'filters'} onOpenChange={(o) => setState(o ? 'filters' : 'browse')} />
    </AppShell>
  );
}
