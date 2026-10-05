'use client';

import { ArrowDown, ArrowUp, FolderHeart, GripVertical, Heart, MoreHorizontal, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { cardLinkOverlay } from '@/components/ui/Card';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconButton } from '@/components/ui/IconButton';
import { Input } from '@/components/ui/Input';
import { Menu } from '@/components/ui/Menu';
import { Textarea } from '@/components/ui/Textarea';
import { useToast } from '@/components/ui/Toast';

import { COLLECTIONS, PLATFORM_SHOTS, TRASH } from '../_components/data';
import { LibraryFrame } from '../_components/LibraryParts';
import { AssetGrid, DurationChip, MediaCard, Poster } from '../_components/Media';
import { MockFrame } from '../_components/MockFrame';
import { AppShell } from '../_components/Shells';
import { Callout } from '../_components/Additions';

const STATES = [
  { id: 'favourites', label: 'Favourites' },
  { id: 'favourites-empty', label: 'Favourites empty' },
  { id: 'collections', label: 'Collections' },
  { id: 'collections-empty', label: 'Collections empty' },
  { id: 'new', label: 'New collection dialog' },
  { id: 'detail', label: 'Collection detail + reorder' },
  { id: 'curated', label: 'Featured (read-only)' },
] as const;

export function LibraryCollections() {
  return (
    <MockFrame title="Library · Favourites and collections" url="/dashboard/library/favourites · /collections[/id]" flag="broll_platform_library or broll_user_library" states={STATES}>
      {(state, setState) => <Body state={state} setState={setState} />}
    </MockFrame>
  );
}

function Body({ state, setState }: { state: string; setState: (s: string) => void }) {
  const { show } = useToast();
  const [order, setOrder] = useState(PLATFORM_SHOTS.slice(0, 5));
  const move = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= order.length) return;
    const next = [...order];
    [next[i], next[j]] = [next[j], next[i]];
    setOrder(next);
    show({ title: `Moved '${order[i].title}' to position ${j + 1}` });
  };
  const favs = [PLATFORM_SHOTS[1], PLATFORM_SHOTS[4], PLATFORM_SHOTS[6], PLATFORM_SHOTS[9]];
  const tab = state.startsWith('favourites') ? 'favourites' : 'collections';

  return (
    <AppShell active="library">
      <LibraryFrame tab={tab}>
        {state === 'favourites' && (
          <AssetGrid
            label="Favourites"
            items={favs}
            renderItem={(i, tabIndex) => {
              const s = favs[i];
              return (
                <MediaCard
                  inGrid
                  tabIndex={tabIndex}
                  title={s.title}
                  duration={s.duration}
                  look={s.look}
                  orientation={s.orientation}
                  favourite
                  onFavourite={() => show({ title: `Removed '${s.title}' from favourites`, action: { label: 'Undo', onClick: () => undefined } })}
                  status={i === 2 ? 'retired' : 'live'}
                  meta={i === 2 ? 'Still plays where you used it' : 'Clipnera library'}
                />
              );
            }}
          />
        )}
        {state === 'favourites-empty' && (
          <EmptyState icon={<Heart />} title="No favourites yet" description="Tap the heart on any clip to keep it here. Favourites are private to you." />
        )}

        {(state === 'collections' || state === 'new') && (
          <div className="space-y-6">
            <div className="flex justify-end">
              <Button leadingIcon={<Plus />} onClick={() => setState('new')}>New collection</Button>
            </div>
            {[{ title: 'Yours', items: COLLECTIONS.filter((c) => !c.curated) }, { title: 'Featured by Clipnera', items: COLLECTIONS.filter((c) => c.curated) }].map((group) => (
              <section key={group.title} aria-labelledby={`g-${group.title}`} className="space-y-3">
                <h2 id={`g-${group.title}`} className="text-cn-title-sm font-semibold text-cn-fg">{group.title}</h2>
                <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                  {group.items.map((c) => (
                    <li key={c.id}>
                      <Card interactive padding="none" className="overflow-hidden">
                        <Poster look={c.cover} className="h-28 w-full" />
                        <div className="flex items-start gap-1 p-3">
                          <div className="min-w-0 flex-1">
                            <a href="#" onClick={(e) => { e.preventDefault(); setState(c.curated ? 'curated' : 'detail'); }} className={`block truncate text-cn-body font-semibold text-cn-fg ${cardLinkOverlay}`}>
                              {c.name}
                            </a>
                            <p className="text-cn-caption text-cn-fg-muted">{c.count} clips{c.curated && ' · Featured'}</p>
                          </div>
                          <div className="relative z-cn-raised">
                            <Menu
                              align="end"
                              items={c.curated
                                ? [{ id: 'copy', label: 'Save a copy', onSelect: () => undefined }, { id: 'ask', label: 'Use in a prompt', onSelect: () => undefined }]
                                : [
                                    { id: 'rename', label: 'Rename', onSelect: () => undefined },
                                    { id: 'ask', label: 'Use in a prompt', onSelect: () => undefined },
                                    { id: 'sep', type: 'separator' },
                                    { id: 'del', label: 'Delete collection', danger: true, onSelect: () => undefined },
                                  ]}
                              trigger={(props) => <IconButton {...props} size="sm" label={`More for ${c.name}`} icon={<MoreHorizontal />} />}
                            />
                          </div>
                        </div>
                      </Card>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
        {state === 'collections-empty' && (
          <EmptyState icon={<FolderHeart />} title="No collections yet" description="Group clips for a project or a series, then ask for them in a prompt: 'use B-roll from Product shots'." action={<Button leadingIcon={<Plus />}>New collection</Button>} />
        )}

        {(state === 'detail' || state === 'curated') && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="text-cn-title font-semibold text-cn-fg">{state === 'curated' ? 'City at night' : 'Product shots'}</h2>
                <p className="text-cn-label text-cn-fg-muted">{state === 'curated' ? 'Featured by Clipnera · 32 clips · you can save a copy to edit it' : '5 clips · only you can see this'}</p>
              </div>
              {state === 'curated' ? <Button>Save a copy</Button> : <Button variant="secondary">Use in a prompt</Button>}
            </div>
            {state === 'curated' ? (
              <AssetGrid label="City at night" items={PLATFORM_SHOTS} renderItem={(i, t) => { const s = PLATFORM_SHOTS[i]; return <MediaCard inGrid tabIndex={t} title={s.title} duration={s.duration} look={s.look} orientation={s.orientation} onFavourite={() => undefined} />; }} />
            ) : (
              <>
                <Callout tone="neutral">Drag the handle to reorder, or use Move up and Move down. The order is the order Clipnera tries them in a prompt.</Callout>
                <ol aria-label="Clips in Product shots, in order" className="divide-y divide-cn-border rounded-cn-lg border border-cn-border">
                  {order.map((s, i) => (
                    <li key={s.id} className="flex items-center gap-3 p-2">
                      <GripVertical aria-hidden className="size-4 shrink-0 cursor-grab text-cn-fg-muted" />
                      <span className="w-6 text-right font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">{i + 1}</span>
                      <span className="relative block h-14 w-8 shrink-0 overflow-hidden rounded-cn-sm"><Poster look={s.look} className="absolute inset-0" /></span>
                      <span className="min-w-0 flex-1 truncate text-cn-body text-cn-fg">{s.title}</span>
                      <DurationChip>{s.duration}</DurationChip>
                      <IconButton size="sm" label={`Move ${s.title} up`} icon={<ArrowUp />} disabled={i === 0} onClick={() => move(i, -1)} />
                      <IconButton size="sm" label={`Move ${s.title} down`} icon={<ArrowDown />} disabled={i === order.length - 1} onClick={() => move(i, 1)} />
                      <IconButton size="sm" label={`Remove ${s.title} from collection`} icon={<Trash2 />} />
                    </li>
                  ))}
                </ol>
              </>
            )}
          </div>
        )}
      </LibraryFrame>

      <Dialog
        open={state === 'new'}
        onOpenChange={(o) => !o && setState('collections')}
        title="New collection"
        footer={<><Button variant="ghost" onClick={() => setState('collections')}>Cancel</Button><Button onClick={() => setState('detail')}>Create collection</Button></>}
      >
        <div className="space-y-4">
          <Input label="Name" required maxLength={120} placeholder="e.g. Product shots" data-autofocus />
          <Textarea label="Description (optional)" maxLength={500} showCount />
          <p className="text-cn-label text-cn-fg-muted"><Badge>Free</Badge> up to 10 collections · <Badge>Pro</Badge> up to 200</p>
        </div>
      </Dialog>
    </AppShell>
  );
}

const TRASH_STATES = [
  { id: 'default', label: 'Recently deleted' },
  { id: 'empty', label: 'Empty' },
  { id: 'confirm-empty', label: 'Empty trash (owner)' },
  { id: 'member', label: 'Member (cannot empty)' },
] as const;

/** `/dashboard/library/trash`. */
export function LibraryTrash() {
  return (
    <MockFrame title="Library · Recently deleted" url="/dashboard/library/trash" flag="broll_user_library" states={TRASH_STATES}>
      {(state, setState) => (
        <AppShell active="library">
          <LibraryFrame tab="trash">
            {state === 'empty' ? (
              <EmptyState icon={<Trash2 />} title="Nothing here" description="Deleted uploads stay here for 30 days so you can restore them. They still count towards storage until then." />
            ) : (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-cn-body text-cn-fg-secondary">3 files · 1.8 GB. Each is deleted for good after 30 days.</p>
                  {state === 'member' ? (
                    <p className="text-cn-label text-cn-fg-muted">Only the workspace owner can empty this.</p>
                  ) : (
                    <Button variant="secondary" onClick={() => setState('confirm-empty')}>Empty now</Button>
                  )}
                </div>
                <ul className="divide-y divide-cn-border rounded-cn-lg border border-cn-border">
                  {TRASH.map((t) => (
                    <li key={t.id} className="flex flex-wrap items-center gap-3 p-3">
                      <span className="relative block h-14 w-8 shrink-0 overflow-hidden rounded-cn-sm opacity-60"><Poster look={t.look} className="absolute inset-0" /></span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-cn-body font-semibold text-cn-fg">{t.title}</p>
                        <p className="text-cn-caption text-cn-fg-muted">
                          <span className="font-cn-mono">{t.size}</span> · {t.daysLeft} days left{t.usedIn ? ' · shows as Missing clip in 1 project' : ''}
                        </p>
                      </div>
                      <Button size="sm" variant="secondary">Restore</Button>
                      {state !== 'member' && <Button size="sm" variant="ghost">Delete now</Button>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </LibraryFrame>
          <Dialog
            open={state === 'confirm-empty'}
            onOpenChange={(o) => !o && setState('default')}
            role="alertdialog"
            title="Delete 3 files for good?"
            description="This frees 1.8 GB and can't be undone. Exported and published videos don't change."
            footer={<><Button variant="ghost" onClick={() => setState('default')}>Keep them</Button><Button variant="danger" onClick={() => setState('empty')}>Delete 3 files</Button></>}
          />
        </AppShell>
      )}
    </MockFrame>
  );
}
