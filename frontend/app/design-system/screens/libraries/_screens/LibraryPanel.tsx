'use client';

import { ChevronDown, ChevronUp, Film, Search, Sparkles, Undo2 } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Chip } from '@/components/ui/Chip';
import { Input } from '@/components/ui/Input';
import { ResultMessage } from '@/components/ui/ResultMessage';
import { Tab, TabList, TabPanel, Tabs } from '@/components/ui/Tabs';
import { useToast } from '@/components/ui/Toast';

import { Callout } from '../_components/Additions';
import { BEACH_MOMENTS, PLATFORM_SHOTS, type SampleShot } from '../_components/data';
import { AssetDrawer } from '../_components/LibraryParts';
import { AssetGrid, DurationChip, MediaCard, Poster } from '../_components/Media';
import { MockFrame } from '../_components/MockFrame';

const STATES = [
  { id: 'panel', label: 'Library panel' },
  { id: 'uploads', label: 'Your uploads tab' },
  { id: 'dragging', label: 'Dragging to timeline' },
  { id: 'why', label: '"Why this clip" card' },
  { id: 'swap', label: 'Swap open' },
  { id: 'swapped', label: 'After swap' },
  { id: 'no-match', label: 'No good match' },
  { id: 'missing', label: 'Missing clip in project' },
  { id: 'details', label: 'Details from panel' },
] as const;

/**
 * The editor's Library panel (left rail tab beside Media) and the content of
 * the "why this clip" + swap card. The editor frame here is a stand-in; the
 * Editor layout, timeline and prompt bar belong to Designer 2.
 */
export function LibraryPanel() {
  return (
    <MockFrame title="Editor · Library panel and B-roll result card" url="/dashboard/editor/[id] (left rail → Library)" flag="broll_platform_library / broll_user_library + agent_editor" states={STATES}>
      {(state, setState) => <Body state={state} setState={setState} />}
    </MockFrame>
  );
}

function Body({ state, setState }: { state: string; setState: (s: string) => void }) {
  const { show } = useToast();
  const [q, setQ] = useState('coffee');
  const [selected, setSelected] = useState<SampleShot>(PLATFORM_SHOTS[1]);
  const shots = PLATFORM_SHOTS.filter((s) => s.orientation === 'portrait');
  const add = (s: SampleShot) =>
    show({ title: `Added '${s.title}' at 0:12`, description: 'Saved as a new version.', action: { label: 'Undo', onClick: () => undefined } });

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <aside aria-label="Library" className="w-full shrink-0 border-b border-cn-border bg-cn-surface lg:w-80 lg:border-b-0 lg:border-r">
        <Tabs key={state === "uploads" ? "u" : "c"} defaultValue={state === "uploads" ? "uploads" : "clipnera"} variant="pill">
          <div className="space-y-3 p-3">
            <TabList label="Library source">
              <Tab value="clipnera">Clipnera</Tab>
              <Tab value="uploads">Uploads</Tab>
              <Tab value="favourites">Favourites</Tab>
              <Tab value="collections">Collections</Tab>
            </TabList>
            <Input aria-label="Search footage" type="search" size="sm" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search footage" leading={<Search aria-hidden className="size-4 text-cn-fg-muted" />} />
            <div className="flex flex-wrap gap-1.5">
              <Chip size="sm" selected>Fits this project</Chip>
              <Chip size="sm">Under 5 s</Chip>
              <Chip size="sm">With people</Chip>
            </div>
          </div>
          <TabPanel value="clipnera" className="px-3 pb-3">
            <AssetGrid
              label="Clipnera library results"
              rowHeight={150}
              items={shots}
              renderItem={(i, tabIndex) => {
                const s = shots[i];
                return <MediaCard inGrid tabIndex={tabIndex} title={s.title} duration={s.duration} look={s.look} orientation={s.orientation} onAdd={() => add(s)} onFavourite={() => undefined} favourite={s.favourite} onOpen={() => { setSelected(s); setState('details'); }} />;
              }}
            />
          </TabPanel>
          <TabPanel value="uploads" className="px-3 pb-3">
            <AssetGrid
              label="Your uploads results"
              rowHeight={150}
              items={BEACH_MOMENTS}
              renderItem={(i, tabIndex) => {
                const s = BEACH_MOMENTS[i];
                return <MediaCard inGrid tabIndex={tabIndex} title={s.title} meta={`in Beach run · ${s.at}`} duration={s.duration} look={s.look} orientation={s.orientation} onAdd={() => add(s)} onOpen={() => { setSelected(s); setState('details'); }} />;
              }}
            />
            <p className="pt-2 text-cn-caption text-cn-fg-muted">Drop video files here to upload. They appear here once ready.</p>
          </TabPanel>
          <TabPanel value="favourites" className="px-3 pb-3">
            <p className="text-cn-label text-cn-fg-muted">4 favourites</p>
          </TabPanel>
          <TabPanel value="collections" className="px-3 pb-3">
            <p className="text-cn-label text-cn-fg-muted">Product shots · Morning routine series</p>
          </TabPanel>
        </Tabs>
      </aside>

      <section aria-label="Editor stand-in" className="flex min-w-0 flex-1 flex-col gap-4 p-4">
        <div className="flex items-center gap-2 text-cn-caption text-cn-fg-muted">
          <Badge>Stand-in</Badge> Preview, timeline and conversation belong to the Editor design (Designer 2).
        </div>

        <div className="rounded-cn-lg border border-dashed border-cn-border-strong p-3">
          <p className="mb-2 text-cn-caption text-cn-fg-muted">Timeline</p>
          <div className="space-y-1.5">
            <div className="relative h-8 rounded-cn-sm bg-cn-accent-subtle">
              {state === 'dragging' && (
                <>
                  <span className="absolute inset-y-0 left-1/4 w-px bg-cn-accent" aria-hidden />
                  <span className="absolute left-1/4 top-0 flex h-8 w-24 items-center gap-1.5 rounded-cn-sm border-2 border-cn-accent-border bg-cn-surface-raised px-1.5 shadow-cn-2">
                    <span className="relative block h-6 w-4 overflow-hidden rounded-cn-xs"><Poster look={PLATFORM_SHOTS[1].look} className="absolute inset-0" /></span>
                    <span className="font-cn-mono text-cn-caption">0:04</span>
                  </span>
                </>
              )}
              <span className="absolute left-2 top-1.5 text-cn-caption text-cn-fg-secondary">B-roll</span>
            </div>
            <div className="h-12 rounded-cn-sm bg-cn-surface-active" />
          </div>
          {state === 'dragging' && <p role="status" className="mt-2 text-cn-label text-cn-fg-secondary">Drop to add at 0:12 on the B-roll track. Snaps to the playhead.</p>}
        </div>

        {state === 'missing' && (
          <div className="flex items-center gap-3 rounded-cn-lg border border-cn-border bg-cn-surface p-3">
            <span className="flex h-14 w-8 items-center justify-center rounded-cn-sm bg-cn-surface-active"><Film aria-hidden className="size-4 text-cn-fg-muted" /></span>
            <div className="min-w-0 flex-1">
              <p className="text-cn-body font-semibold text-cn-fg">Missing clip at 0:12</p>
              <p className="text-cn-label text-cn-fg-muted">'Rooftop timelapse' was deleted. Exports leave it out until you replace it.</p>
            </div>
            <Button size="sm" variant="secondary">Replace</Button>
            <Button size="sm" variant="ghost">Remove</Button>
          </div>
        )}

        {state === 'no-match' && (
          <ResultMessage
            status="partial"
            summary="Added captions. I couldn't add B-roll of a red vintage tractor."
            notDone={[{ label: 'B-roll at 0:12', reason: "No shot in either library is close enough. A wrong shot would be worse than none." }]}
            suggestions={['Add B-roll of a farm field at 0:12', 'Make an AI shot of a red tractor · 120 credits']}
          />
        )}

        {['why', 'swap', 'swapped'].includes(state) && (
          <div className="max-w-xl space-y-3">
            <ResultMessage
              status="done"
              summary={state === 'swapped' ? 'Swapped B-roll at 0:12.' : 'Added B-roll at 0:12–0:16.'}
              version={{ name: state === 'swapped' ? 'Swapped B-roll at 0:12' : 'Added B-roll of coffee being poured', onUndo: () => undefined, onCompare: () => undefined }}
            />
            <WhyCard swapOpen={state === 'swap'} onToggle={() => setState(state === 'swap' ? 'why' : 'swap')} onSwap={() => setState('swapped')} swapped={state === 'swapped'} />
          </div>
        )}

        {state === 'panel' || state === 'uploads' ? (
          <Callout tone="neutral">Drag a tile onto the timeline, press A or "+" to add it at the playhead, or select it to attach it to your prompt as an Asset chip.</Callout>
        ) : null}
      </section>

      <AssetDrawer context="editor" shot={selected} open={state === 'details'} onOpenChange={(o) => !o && setState('panel')} />
    </div>
  );
}

/** The "why this clip" + swap card (05 §8.3). Sits directly under the run's ResultMessage. */
function WhyCard({ swapOpen, onToggle, onSwap, swapped }: { swapOpen: boolean; onToggle: () => void; onSwap: () => void; swapped: boolean }) {
  const chosen = swapped ? PLATFORM_SHOTS[3] : BEACH_MOMENTS[0];
  const alternates = [PLATFORM_SHOTS[1], PLATFORM_SHOTS[3], PLATFORM_SHOTS[9], BEACH_MOMENTS[2]];
  return (
    <article aria-label={`B-roll used: ${chosen.title}`} className="space-y-3 rounded-cn-lg border border-cn-border bg-cn-surface p-3">
      <div className="flex gap-3">
        <span className="relative block h-20 w-12 shrink-0 overflow-hidden rounded-cn-sm">
          <Poster look={chosen.look} className="absolute inset-0" />
          <span className="absolute bottom-0.5 right-0.5"><DurationChip>0:04</DurationChip></span>
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-cn-body text-cn-fg">
            &ldquo;{chosen.caption}&rdquo; from <b>{chosen.scope === 'mine' ? 'your uploads' : 'the Clipnera library'}</b>
          </p>
          <p className="flex flex-wrap items-center gap-1.5 text-cn-label text-cn-fg-secondary">
            <Sparkles aria-hidden className="size-3.5 text-cn-fg-muted" />
            <span className="sr-only">Why:</span>
            {swapped ? (
              <Badge>Chosen by you</Badge>
            ) : (
              <>
                <Badge>Matches &lsquo;coffee&rsquo; and &lsquo;pour&rsquo;</Badge>
                <Badge>From your library</Badge>
                <Badge>Fits 9:16</Badge>
              </>
            )}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" trailingIcon={swapOpen ? <ChevronUp /> : <ChevronDown />} aria-expanded={swapOpen} aria-controls="swap-strip" onClick={onToggle}>
          Swap
        </Button>
        <Button size="sm" variant="ghost" leadingIcon={<Undo2 />}>Remove B-roll</Button>
      </div>
      {swapOpen && (
        <div id="swap-strip" className="space-y-2">
          <p className="text-cn-label text-cn-fg-muted">Other good matches. Picking one saves a new version.</p>
          <ul className="grid grid-cols-4 gap-2" aria-label="Alternatives">
            {alternates.map((a) => (
              <li key={a.id}>
                <MediaCard title={a.title} duration={a.duration} look={a.look} orientation="portrait" meta={a.scope === 'mine' ? 'Your uploads' : 'Clipnera'} onOpen={onSwap} />
              </li>
            ))}
          </ul>
          <Button size="sm" variant="ghost" leadingIcon={<Search />}>Search for something else</Button>
        </div>
      )}
    </article>
  );
}
