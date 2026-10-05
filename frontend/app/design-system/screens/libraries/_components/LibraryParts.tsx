'use client';

import { ArrowUpDown, Copy, Flag, FolderPlus, Heart, Play, Search, SlidersHorizontal, Upload, X } from 'lucide-react';
import { type ReactNode, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Chip } from '@/components/ui/Chip';
import { Dialog } from '@/components/ui/Dialog';
import { Drawer } from '@/components/ui/Drawer';
import { IconButton } from '@/components/ui/IconButton';
import { Input } from '@/components/ui/Input';
import { Menu, type MenuEntry } from '@/components/ui/Menu';
import { Textarea } from '@/components/ui/Textarea';
import { useToast } from '@/components/ui/Toast';

import { KeyValues, RadioGroup, StorageMeter } from './Additions';
import { type SampleShot, PLATFORM_SHOTS } from './data';
import { DurationChip, MediaCard, Poster, RATIO } from './Media';
import { NavTabs, PageBody, ScreenHeader } from './Shells';

export type LibraryTab = 'clipnera' | 'uploads' | 'favourites' | 'collections' | 'trash';

/** Header, storage meter and section tabs shared by every /dashboard/library page. */
export function LibraryFrame({
  tab,
  userLibrary = true,
  platformLibrary = true,
  storage = { used: 3.2, total: 25 },
  uploadDisabled,
  children,
}: {
  tab: LibraryTab;
  userLibrary?: boolean;
  platformLibrary?: boolean;
  storage?: { used: number; total: number };
  uploadDisabled?: string;
  children: ReactNode;
}) {
  const tabs = [
    platformLibrary && { id: 'clipnera', label: 'Clipnera library' },
    userLibrary && { id: 'uploads', label: 'Your uploads', count: 6 },
    { id: 'favourites', label: 'Favourites', count: 4 },
    { id: 'collections', label: 'Collections' },
    userLibrary && { id: 'trash', label: 'Recently deleted', count: 3 },
  ].filter(Boolean) as { id: string; label: string; count?: number }[];

  return (
    <PageBody>
      <ScreenHeader
        title="Library"
        description="Footage for any project: shots curated by Clipnera and clips you upload. Drag one into the editor, or ask for it in a prompt."
        actions={
          userLibrary && (
            <>
              <div className="hidden md:block">
                <StorageMeter compact used={storage.used} total={storage.total} />
              </div>
              <Button
                variant={tab === 'uploads' ? 'primary' : 'secondary'}
                leadingIcon={<Upload />}
                aria-disabled={uploadDisabled ? true : undefined}
                aria-describedby={uploadDisabled ? 'upload-disabled-reason' : undefined}
                className={uploadDisabled ? 'cursor-not-allowed opacity-50' : undefined}
              >
                Upload
              </Button>
              {uploadDisabled && (
                <span id="upload-disabled-reason" className="sr-only">
                  {uploadDisabled}
                </span>
              )}
            </>
          )
        }
      />
      <NavTabs label="Library sections" items={tabs} active={tab} />
      {children}
    </PageBody>
  );
}

const FILTERS: ReadonlyArray<{ id: string; label: string; options: readonly string[] }> = [
  { id: 'orientation', label: 'Orientation', options: ['Vertical', 'Square', 'Horizontal'] },
  { id: 'duration', label: 'Duration', options: ['Under 5 s', '5–10 s', '10–20 s', 'Over 20 s'] },
  { id: 'resolution', label: 'Resolution', options: ['HD (720p+)', 'Full HD (1080p+)', '4K'] },
  { id: 'colour', label: 'Colour', options: ['Warm', 'Cool', 'Neutral', 'Black and white', 'Vivid'] },
  { id: 'mood', label: 'Mood', options: ['Calm', 'Energetic', 'Dramatic', 'Hopeful', 'Dark', 'Playful', 'Professional'] },
  { id: 'people', label: 'People', options: ['With people', 'No people'] },
  { id: 'source', label: 'Source', options: ['Clipnera library', 'Your uploads', 'AI shots'] },
];

/**
 * Search box, filter chips (each a menu of checkable values), sort, and
 * "No attribution needed". On phones the chips fold into one "Filters"
 * button that opens a bottom sheet.
 */
export function SearchToolbar({
  query,
  onQuery,
  placeholder = "Search footage — try 'drone shot of a city at night'",
  showSource = true,
  active = { orientation: ['Vertical'] },
  onOpenSheet,
}: {
  query: string;
  onQuery: (q: string) => void;
  placeholder?: string;
  showSource?: boolean;
  active?: Record<string, string[]>;
  onOpenSheet?: () => void;
}) {
  const [selected, setSelected] = useState<Record<string, string[]>>(active);
  const [sort, setSort] = useState('Best match');
  const count = Object.values(selected).flat().length;
  const toggle = (id: string, value: string) =>
    setSelected((s) => {
      const current = s[id] ?? [];
      return { ...s, [id]: current.includes(value) ? current.filter((v) => v !== value) : [...current, value] };
    });

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <Input
          aria-label="Search footage"
          type="search"
          value={query}
          onChange={(e) => onQuery(e.target.value)}
          placeholder={placeholder}
          leading={<Search aria-hidden className="size-4 text-cn-fg-muted" />}
          trailing={query ? <IconButton size="sm" label="Clear search" icon={<X />} onClick={() => onQuery('')} /> : undefined}
          className="flex-1"
          size="lg"
        />
        <Button size="lg" variant="secondary" className="md:hidden" leadingIcon={<SlidersHorizontal />} onClick={onOpenSheet}>
          Filters{count > 0 && ` · ${count}`}
        </Button>
      </div>
      <div className="hidden flex-wrap items-center gap-2 md:flex">
        {FILTERS.filter((f) => showSource || f.id !== 'source').map((filter) => {
          const values = selected[filter.id] ?? [];
          const items: MenuEntry[] = filter.options.map((option) => ({
            id: option,
            label: option,
            checked: values.includes(option),
            onSelect: () => toggle(filter.id, option),
          }));
          return (
            <Menu
              key={filter.id}
              items={items}
              trigger={(props) => (
                <Chip {...props} selected={values.length > 0} size="sm">
                  {values.length ? `${filter.label}: ${values.join(', ')}` : filter.label}
                </Chip>
              )}
            />
          );
        })}
        <Chip size="sm" selected={!!selected.attribution?.length} onClick={() => toggle('attribution', 'yes')}>
          No attribution needed
        </Chip>
        {count > 0 && (
          <Button size="sm" variant="ghost" onClick={() => setSelected({})}>
            Clear filters
          </Button>
        )}
        <span className="flex-1" />
        <Menu
          align="end"
          items={['Best match', 'Newest', 'Most used', 'Shortest first'].map((s) => ({ id: s, label: s, checked: sort === s, onSelect: () => setSort(s) }))}
          trigger={(props) => (
            <Button {...props} size="sm" variant="ghost" leadingIcon={<ArrowUpDown />}>
              {sort}
            </Button>
          )}
        />
      </div>
    </div>
  );
}

/** The phone filter sheet: every filter as a group of toggle chips, Apply at the bottom. */
export function FilterSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [picked, setPicked] = useState<string[]>(['Vertical']);
  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      side="bottom"
      title="Filters"
      footer={
        <>
          <Button variant="ghost" onClick={() => setPicked([])}>
            Clear all
          </Button>
          <Button onClick={() => onOpenChange(false)}>Show 48 shots</Button>
        </>
      }
    >
      <div className="space-y-5">
        {FILTERS.map((filter) => (
          <div key={filter.id} role="group" aria-labelledby={`sheet-${filter.id}`} className="space-y-2">
            <p id={`sheet-${filter.id}`} className="text-cn-label font-semibold text-cn-fg">
              {filter.label}
            </p>
            <div className="flex flex-wrap gap-2">
              {filter.options.map((option) => (
                <Chip
                  key={option}
                  selected={picked.includes(option)}
                  onClick={() => setPicked((p) => (p.includes(option) ? p.filter((x) => x !== option) : [...p, option]))}
                >
                  {option}
                </Chip>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Drawer>
  );
}

/**
 * Details drawer (05 §3.2 / §3.3). One component for both libraries; the
 * licence block shows only for Clipnera library shots, and own uploads get
 * editable title and tags, "Used in", Download and Delete instead.
 */
export function AssetDrawer({
  shot,
  open,
  onOpenChange,
  context = 'page',
  onReport,
}: {
  shot: SampleShot;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** `page` = /dashboard/library; `editor` = the editor's Library panel. */
  context?: 'page' | 'editor';
  onReport?: () => void;
}) {
  const { show } = useToast();
  const mine = shot.scope === 'mine';
  const copy = () => show({ title: 'Credit line copied', tone: 'success' });

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      side="right"
      size="lg"
      title={shot.title}
      description={mine ? `From ${shot.sourceTitle ?? 'your uploads'}${shot.at ? ` at ${shot.at}` : ''}` : 'Clipnera library'}
      footer={
        <>
          <Menu
            side="top"
            items={[
              { id: 'new', label: 'New collection…', onSelect: () => undefined },
              { id: 'sep', type: 'separator' },
              { id: 'c1', label: 'Product shots', onSelect: () => show({ title: 'Added to Product shots', tone: 'success' }) },
              { id: 'c2', label: 'Morning routine series', onSelect: () => undefined },
            ]}
            trigger={(props) => (
              <Button {...props} variant="secondary" leadingIcon={<FolderPlus />}>
                Add to collection
              </Button>
            )}
          />
          {context === 'editor' ? (
            <Button>Add at playhead</Button>
          ) : (
            <Menu
              side="top"
              align="end"
              items={[
                { id: 'l', type: 'label', label: 'Open in a project' },
                { id: 'p1', label: 'Morning routine — ep 4', onSelect: () => undefined },
                { id: 'p2', label: 'Podcast #31 with Anil', onSelect: () => undefined },
                { id: 'p3', label: 'Choose another project…', onSelect: () => undefined },
              ]}
              trigger={(props) => <Button {...props}>Use in a project</Button>}
            />
          )}
        </>
      }
    >
      <div className="space-y-6">
        <div className="relative mx-auto overflow-hidden rounded-cn-lg bg-cn-overlay" style={{ aspectRatio: String(RATIO[shot.orientation]), maxHeight: '22rem' }}>
          <Poster look={shot.look} className="absolute inset-0" />
          <div className="absolute inset-x-2 bottom-2 flex items-center gap-2 rounded-cn-md bg-cn-bg/80 px-2 py-1.5">
            <IconButton size="sm" label="Play preview" icon={<Play />} />
            <span className="h-1 flex-1 rounded-cn-full bg-cn-surface-active">
              <span className="block h-full w-1/3 rounded-cn-full bg-cn-accent" />
            </span>
            <span className="font-cn-mono text-cn-caption tabular-nums text-cn-fg">0:03 / {shot.duration}</span>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <IconButton variant="secondary" label={shot.favourite ? 'Remove from favourites' : 'Add to favourites'} pressed={shot.favourite} icon={<Heart className={shot.favourite ? 'fill-current' : undefined} />} />
          {!mine && (
            <Button variant="ghost" leadingIcon={<Flag />} onClick={onReport}>
              Report a problem
            </Button>
          )}
        </div>

        <section aria-labelledby="asset-about" className="space-y-2">
          <h3 id="asset-about" className="text-cn-label font-semibold text-cn-fg">
            About this shot
          </h3>
          <p className="text-cn-body text-cn-fg-secondary">{shot.caption}.</p>
          <ul aria-label="Tags" className="flex flex-wrap gap-1.5">
            {['night', 'city', 'aerial', 'lights', 'urban'].map((tag) => (
              <li key={tag}>
                <Badge>{tag}</Badge>
              </li>
            ))}
          </ul>
          <KeyValues
            items={[
              { label: 'Duration', value: <span className="font-cn-mono tabular-nums">{shot.duration}</span> },
              { label: 'Resolution', value: <span className="font-cn-mono tabular-nums">1080 × 1920</span> },
              { label: 'Orientation', value: 'Vertical (fits 9:16 projects)' },
              { label: 'Mood', value: 'Calm' },
              {
                label: 'Colours',
                value: (
                  <span className="inline-flex gap-1">
                    {shot.look.map((c) => (
                      <span key={c} aria-hidden className="size-4 rounded-cn-xs border border-cn-border" style={{ background: c }} />
                    ))}
                    <span className="sr-only">Cool, dark blues with amber highlights</span>
                  </span>
                ),
              },
            ]}
          />
        </section>

        {!mine && shot.licence && (
          <section aria-labelledby="asset-licence" className="space-y-3 rounded-cn-lg border border-cn-border p-4">
            <h3 id="asset-licence" className="text-cn-label font-semibold text-cn-fg">
              Licence
            </h3>
            <KeyValues
              items={[
                { label: 'Author', value: <a href="#" className="text-cn-accent-text underline underline-offset-2">{shot.licence.author}</a> },
                { label: 'Licence', value: <a href="#" className="text-cn-accent-text underline underline-offset-2">{shot.licence.name}</a> },
                { label: 'Credit', value: shot.licence.required ? 'Required — added to your export credits' : 'Not required, offered' },
              ]}
            />
            {shot.licence.attribution && (
              <div className="flex items-center gap-2 rounded-cn-md bg-cn-surface-hover px-3 py-2">
                <p className="min-w-0 flex-1 truncate font-cn-mono text-cn-caption text-cn-fg">{shot.licence.attribution}</p>
                <Button size="sm" variant="ghost" leadingIcon={<Copy />} onClick={copy}>
                  Copy
                </Button>
              </div>
            )}
            <p className="text-cn-label text-cn-fg-muted">
              Use in your videos: yes. Download: not available — Clipnera library footage is only used inside your exports.
            </p>
          </section>
        )}

        <section aria-labelledby="asset-similar" className="space-y-2">
          <h3 id="asset-similar" className="text-cn-label font-semibold text-cn-fg">
            Similar shots
          </h3>
          <ul className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
            {PLATFORM_SHOTS.slice(2, 7).map((s) => (
              <li key={s.id}>
                <button type="button" aria-label={`${s.title}, ${s.duration}`} className="relative block w-20 overflow-hidden rounded-cn-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cn-focus" style={{ aspectRatio: '9 / 16' }}>
                  <Poster look={s.look} className="absolute inset-0" />
                  <span className="absolute bottom-1 right-1">
                    <DurationChip>{s.duration}</DurationChip>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </Drawer>
  );
}

const REPORT_REASONS = [
  { value: 'wrong_tags', label: 'Wrong tags or description' },
  { value: 'low_quality', label: 'Low quality' },
  { value: 'offensive', label: 'Offensive or harmful' },
  { value: 'copyright', label: 'Copyright or licence problem' },
  { value: 'other', label: 'Something else' },
] as const;

/** ReportCreate (05 §7.3): reason + optional note. */
export function ReportDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [reason, setReason] = useState<(typeof REPORT_REASONS)[number]['value'] | null>(null);
  const [tried, setTried] = useState(false);
  const { show } = useToast();
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Report a problem with this shot"
      description="We review every report. The shot stays in your projects while we check."
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              setTried(true);
              if (!reason) return;
              onOpenChange(false);
              show({ title: 'Report sent', description: 'Thanks. We look at reports within 2 working days.', tone: 'success' });
            }}
          >
            Send report
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <RadioGroup legend="What's wrong?" options={REPORT_REASONS} value={reason} onValueChange={setReason} error={tried && !reason ? 'Choose a reason.' : undefined} />
        <Textarea label="Anything else? (optional)" maxLength={500} showCount placeholder="For example, the tags say 'Delhi' but this is Mumbai." />
      </div>
    </Dialog>
  );
}

/** Small reusable tile for horizontal "featured" rows. */
export function FeaturedTile({ shot, onOpen }: { shot: SampleShot; onOpen: () => void }) {
  return (
    <li>
      <MediaCard fixedWidth title={shot.title} duration={shot.duration} look={shot.look} orientation="portrait" favourite={shot.favourite} onFavourite={() => undefined} onOpen={onOpen} />
    </li>
  );
}
