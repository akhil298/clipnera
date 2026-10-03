'use client';

import { Download, Eye, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { Dialog } from '@/components/ui/Dialog';
import { Drawer } from '@/components/ui/Drawer';
import { Input } from '@/components/ui/Input';
import { Skeleton, SkeletonGroup } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';

import { Callout, Dropzone, KeyValues, StorageMeter } from '../_components/Additions';
import { BEACH_MOMENTS, MY_SOURCES } from '../_components/data';
import { LibraryFrame, SearchToolbar } from '../_components/LibraryParts';
import { AssetGrid, MediaCard, Poster, RATIO } from '../_components/Media';
import { MockFrame } from '../_components/MockFrame';
import { AppShell } from '../_components/Shells';
import { ALL_TRAY_ROWS, UploadTray } from '../_components/UploadTray';

const STATES = [
  { id: 'default', label: 'Your uploads' },
  { id: 'expanded', label: "File expanded to shots" },
  { id: 'empty', label: 'Empty (first use)' },
  { id: 'dragging', label: 'Dragging files over' },
  { id: 'rights', label: 'Rights confirmation (first upload)' },
  { id: 'tray', label: 'Upload tray, every row state' },
  { id: 'near-quota', label: 'Storage 84%' },
  { id: 'over-quota', label: 'Over quota (uploads blocked)' },
  { id: 'held', label: 'Held for review' },
  { id: 'details', label: 'Own item drawer' },
  { id: 'delete', label: 'Delete (used in 2 projects)' },
  { id: 'loading', label: 'Loading' },
  { id: 'error', label: 'Load failed' },
  { id: 'viewer', label: 'Viewer role (read only)' },
  { id: 'flag-off', label: 'Uploads flag off' },
] as const;

export function LibraryUploads() {
  return (
    <MockFrame title="Library · Your uploads" url="/dashboard/library/uploads" flag="broll_user_library" states={STATES}>
      {(state, setState) => <Body state={state} setState={setState} />}
    </MockFrame>
  );
}

function Body({ state, setState }: { state: string; setState: (s: string) => void }) {
  const { show } = useToast();
  const [query, setQuery] = useState('');
  const [rights, setRights] = useState(false);
  const [rightsTried, setRightsTried] = useState(false);
  const storage = state === 'near-quota' ? { used: 21, total: 25 } : state === 'over-quota' ? { used: 25.4, total: 25 } : { used: 3.2, total: 25 };
  const readOnly = state === 'viewer' || state === 'flag-off';
  const blocked = state === 'over-quota' ? 'Uploads are paused: your library is full.' : readOnly ? (state === 'viewer' ? 'Viewers can browse but not upload.' : 'Uploads are paused for now.') : undefined;
  const sources = state === 'held' ? MY_SOURCES : MY_SOURCES.filter((s) => s.state !== 'held');

  return (
    <AppShell active="library">
      <LibraryFrame tab="uploads" storage={storage} uploadDisabled={blocked}>
        {state === 'near-quota' && (
          <Callout tone="warning" title="You've used 21 GB of 25 GB." action={<Button size="sm" variant="secondary">Review large files</Button>}>
            Uploads keep working until the library is full. Deleting files in Recently deleted frees space at once.
          </Callout>
        )}
        {state === 'over-quota' && (
          <Callout tone="danger" title="Uploads paused — your library is full." action={<><Button size="sm" variant="secondary">Free up space</Button><Button size="sm">See Pro storage</Button></>}>
            25.4 GB of 25 GB used. Your clips are safe: nothing is deleted, and footage already in projects keeps working.
          </Callout>
        )}
        {state === 'flag-off' && (
          <Callout tone="neutral" title="Uploads are paused for now.">
            Your files are safe and still play in your projects. You can still download or delete them.
          </Callout>
        )}
        {state === 'viewer' && (
          <Callout tone="neutral" title="You can browse this library.">
            Only members and the owner of this workspace can upload, rename or delete. Ask the owner to change your role.
          </Callout>
        )}
        {state === 'held' && (
          <Callout tone="danger" title="'Night drive' is held for review.">
            It can't be used until we check it — usually within a day. You'll get a notification either way.
          </Callout>
        )}
        {state === 'error' && (
          <Callout tone="danger" live="alert" title="Your uploads didn't load." action={<Button size="sm" variant="secondary">Try again</Button>}>
            Your files are safe. Uploads in progress keep going.
          </Callout>
        )}

        {(state === 'empty' || state === 'dragging') && (
          <div className="space-y-3">
            <Dropzone
              dragging={state === 'dragging'}
              title="Upload your own footage — it stays private to you"
              hint="Drop video files here or choose them. MP4, MOV, WebM or MKV · up to 4 GB and 30 min each · 25 GB on Pro."
              accept="video/mp4,video/quicktime,video/webm,video/x-matroska"
              multiple
            />
            <p className="text-center text-cn-label text-cn-fg-muted">Clipnera describes each file and splits it into shots, so you can search them by what's on screen.</p>
          </div>
        )}

        {state === 'loading' && (
          <SkeletonGroup label="Loading your uploads" className="flex flex-wrap gap-2">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="w-36 space-y-2 p-1.5">
                <Skeleton className="w-full rounded-cn-md" style={{ aspectRatio: '9 / 16' }} />
                <Skeleton className="h-3 w-3/4" />
              </div>
            ))}
          </SkeletonGroup>
        )}

        {!['empty', 'dragging', 'loading', 'error'].includes(state) && (
          <div className="space-y-4">
            <SearchToolbar query={query} onQuery={setQuery} placeholder="Search your uploads — try 'the part where I'm running'" showSource={false} active={{}} />
            <div className="flex flex-wrap gap-2 text-cn-label text-cn-fg-muted">
              <span>{sources.length} files · 14 shots</span>
            </div>
            <AssetGrid
              label="Your uploads"
              items={sources}
              renderItem={(i, tabIndex) => {
                const s = sources[i];
                return (
                  <MediaCard
                    inGrid
                    tabIndex={tabIndex}
                    title={s.title}
                    duration={s.duration}
                    look={s.look}
                    orientation={s.orientation}
                    status={s.state === 'processing' ? 'processing' : s.state === 'held' ? 'held' : 'live'}
                    step={s.step}
                    meta={s.kind === 'generated' ? 'AI shot' : `${s.size}${s.usedIn ? ` · in ${s.usedIn} project${s.usedIn > 1 ? 's' : ''}` : ''}`}
                    badge={s.shots > 1 ? <Badge>{s.shots} shots</Badge> : undefined}
                    favourite={s.favourite}
                    onFavourite={() => undefined}
                    selectable={!readOnly}
                    onOpen={() => setState(s.shots > 1 && i === 0 ? 'expanded' : 'details')}
                    menu={[
                      { id: 'open', label: 'Details', onSelect: () => setState('details') },
                      { id: 'shots', label: 'Show shots', disabled: s.shots < 2, onSelect: () => setState('expanded') },
                      { id: 'dl', label: 'Download original', onSelect: () => undefined },
                      { id: 'sep', type: 'separator' },
                      { id: 'del', label: 'Delete…', danger: true, disabled: state === 'viewer', onSelect: () => setState('delete') },
                    ]}
                  />
                );
              }}
            />
            {state === 'expanded' && (
              <section aria-labelledby="moments" className="space-y-3 rounded-cn-xl border border-cn-border bg-cn-surface p-4">
                <div className="flex items-center justify-between gap-2">
                  <h2 id="moments" className="text-cn-body font-semibold text-cn-fg">
                    Beach run · 6 shots
                  </h2>
                  <Button size="sm" variant="ghost" onClick={() => setState('default')}>
                    Collapse
                  </Button>
                </div>
                <AssetGrid
                  label="Shots in Beach run"
                  rowHeight={180}
                  items={BEACH_MOMENTS}
                  renderItem={(i, tabIndex) => {
                    const m = BEACH_MOMENTS[i];
                    return <MediaCard inGrid tabIndex={tabIndex} title={m.title} meta={`in Beach run · ${m.at}`} duration={m.duration} look={m.look} orientation={m.orientation} onFavourite={() => undefined} onOpen={() => setState('details')} />;
                  }}
                />
              </section>
            )}
          </div>
        )}
      </LibraryFrame>

      {state === 'tray' && <UploadTray rows={ALL_TRAY_ROWS} />}

      <Dialog
        open={state === 'rights'}
        onOpenChange={(o) => !o && setState('default')}
        title="Before your first upload"
        description="Your uploads are private to you. Only you can see or use them."
        footer={
          <>
            <Button variant="ghost" onClick={() => setState('default')}>Cancel</Button>
            <Button
              onClick={() => {
                setRightsTried(true);
                if (rights) setState('tray');
              }}
            >
              Upload 3 files
            </Button>
          </>
        }
      >
        <Checkbox
          checked={rights}
          onChange={(e) => setRights(e.target.checked)}
          label="I own this footage or have permission to use it."
          description="We ask once. Footage that breaks our Terms can be taken down."
          error={rightsTried && !rights ? 'Tick this to upload.' : undefined}
        />
      </Dialog>

      <Dialog
        open={state === 'delete'}
        onOpenChange={(o) => !o && setState('default')}
        role="alertdialog"
        title="Delete 'Beach run'?"
        description="Used in 2 projects. Those projects will show 'Missing clip' where it was. Videos you've already exported or published don't change."
        footer={
          <>
            <Button variant="ghost" onClick={() => setState('default')}>Keep file</Button>
            <Button variant="secondary" onClick={() => { setState('default'); show({ title: "Deleted 'Beach run' now", description: '412 MB freed.', tone: 'success' }); }}>
              Delete now
            </Button>
            <Button variant="danger" onClick={() => { setState('default'); show({ title: "Moved 'Beach run' to Recently deleted", description: 'Restore it within 30 days.', action: { label: 'Undo', onClick: () => undefined } }); }}>
              Move to Recently deleted
            </Button>
          </>
        }
      >
        <ul className="space-y-1 text-cn-body text-cn-fg-secondary">
          <li>· Morning routine — ep 4</li>
          <li>· Podcast #31 with Anil</li>
        </ul>
        <p className="mt-3 text-cn-label text-cn-fg-muted">Recently deleted still counts towards storage. "Delete now" frees 412 MB at once and can't be undone.</p>
      </Dialog>

      <Drawer
        open={state === 'details'}
        onOpenChange={(o) => !o && setState('default')}
        size="lg"
        title="Beach run"
        description="Uploaded 2 Oct · 6 shots"
        footer={
          <>
            <Button variant="ghost" leadingIcon={<Trash2 />} onClick={() => setState('delete')}>Delete…</Button>
            <Button variant="secondary" leadingIcon={<Download />}>Download</Button>
            <Button>Save changes</Button>
          </>
        }
      >
        <div className="space-y-6">
          <div className="relative mx-auto max-h-80 overflow-hidden rounded-cn-lg" style={{ aspectRatio: String(RATIO.portrait) }}>
            <Poster look={MY_SOURCES[0].look} className="absolute inset-0" />
          </div>
          <Input label="Title" defaultValue="Beach run" />
          <div className="space-y-2">
            <p className="text-cn-label font-semibold text-cn-fg">Tags</p>
            <ul className="flex flex-wrap gap-1.5" aria-label="Tags (added by Clipnera; remove any that are wrong)">
              {['beach', 'running', 'sunrise', 'sea', 'fitness'].map((t) => (
                <li key={t}>
                  <span className="inline-flex h-7 items-center gap-1 rounded-cn-full border border-cn-border bg-cn-surface pl-2.5 pr-1 text-cn-label text-cn-fg">
                    {t}
                    <button type="button" aria-label={`Remove tag ${t}`} className="inline-flex size-5 items-center justify-center rounded-cn-full text-cn-fg-muted hover:bg-cn-surface-hover hover:text-cn-fg">×</button>
                  </span>
                </li>
              ))}
            </ul>
            <Input aria-label="Add a tag" placeholder="Add a tag and press Enter" size="sm" />
          </div>
          <section aria-labelledby="used-in" className="space-y-2">
            <h3 id="used-in" className="text-cn-label font-semibold text-cn-fg">Used in</h3>
            <ul className="space-y-1 text-cn-body">
              <li><a href="#" className="text-cn-accent-text underline underline-offset-2">Morning routine — ep 4</a> <span className="text-cn-fg-muted">· Editor project</span></li>
              <li><a href="#" className="text-cn-accent-text underline underline-offset-2">Podcast #31 with Anil</a> <span className="text-cn-fg-muted">· Clip</span></li>
            </ul>
          </section>
          <KeyValues
            items={[
              { label: 'Length', value: <span className="font-cn-mono">2:41</span> },
              { label: 'Original', value: '3840 × 2160 · HEVC · 1.9 GB' },
              { label: 'Stored as', value: '1080 × 1920 copy · 412 MB' },
              { label: 'Audio', value: 'Yes' },
            ]}
          />
          <p className="flex items-start gap-2 text-cn-label text-cn-fg-muted">
            <Eye aria-hidden className="mt-0.5 size-4 shrink-0" /> We store a 1080p copy to save space. Download gives you that copy; keep your original on your device.
          </p>
          <StorageMeter used={storage.used} total={storage.total} breakdown={[{ label: 'Uploads', value: 2.6 }, { label: 'AI shots', value: 0.2 }, { label: 'Recently deleted', value: 0.4 }]} />
        </div>
      </Drawer>
    </AppShell>
  );
}
