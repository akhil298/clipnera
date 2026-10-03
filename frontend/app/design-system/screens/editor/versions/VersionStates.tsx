'use client';

import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Skeleton, SkeletonGroup } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';

import { PreviewPlayer } from '../_components/PreviewPlayer';
import { VERSIONS } from '../_components/sample';
import { ScreenShell, StateSwitcher } from '../_components/ScreenShell';
import { VersionHistoryList } from '../_components/VersionHistory';

const STATES = [
  { value: 'list', label: 'History open' },
  { value: 'viewing', label: 'Viewing read-only' },
  { value: 'compare', label: 'Compare side by side' },
  { value: 'loading', label: 'Loading' },
  { value: 'conflict', label: 'Undo would discard hand edits' },
];

export function VersionStates() {
  const toast = useToast();
  const [state, setState] = useState('list');
  const [versions, setVersions] = useState(VERSIONS);
  const [viewingId, setViewingId] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const viewing = state === 'viewing' ? versions.find((version) => version.id === (viewingId ?? 'v10')) : undefined;

  const restore = (id: string) => {
    setRestoringId(id);
    setTimeout(() => {
      const source = versions.find((version) => version.id === id);
      setVersions([{ id: `r${Date.now()}`, name: `Restored “${source?.name}”`, author: 'You', time: 'Just now', exact: 'Now', current: true, kind: 'restore' }, ...versions.map((version) => ({ ...version, current: false }))]);
      setRestoringId(null);
      setState('list');
      toast.show({ title: `Restored “${source?.name}”`, description: 'It’s now the newest version. Nothing was deleted.', tone: 'success' });
    }, 900);
  };

  return (
    <ScreenShell
      title="Version history"
      summary="One prompt, one version. Look without changing, restore, compare, bookmark."
      flags={['new_ui_editor_timeline']}
      controls={<StateSwitcher label="State" options={STATES} value={state} onChange={setState} />}
    >
      <div className="grid gap-6 lg:grid-cols-[1fr_26rem]">
        <div className="h-[40rem] overflow-hidden rounded-cn-xl border border-cn-border">
          <PreviewPlayer
            time={8}
            length={30}
            playing={false}
            onPlayPause={() => undefined}
            onSeek={() => undefined}
            quality="full"
            captions={state !== 'viewing'}
            title={null}
            broll={false}
            viewing={viewing ? { name: viewing.name, onBack: () => setState('list'), onRestore: () => restore(viewing.id) } : null}
            compare={state === 'compare' ? 'side' : 'off'}
            before={{ captions: false, title: null, broll: false, name: 'Moved the title down · 6 min ago' }}
            className="h-full"
          />
        </div>
        <aside aria-label="Version history" className="rounded-cn-xl border border-cn-border-strong bg-cn-surface-raised p-4 shadow-cn-2">
          <h2 className="mb-1 text-cn-title-sm font-semibold">Version history</h2>
          <p className="mb-4 text-cn-label text-cn-fg-muted">Why ₹499 works · shown as a right drawer (bottom sheet on phones)</p>
          {state === 'loading' ? (
            <SkeletonGroup label="Loading versions" className="flex flex-col gap-3">
              {Array.from({ length: 5 }, (_, index) => (
                <div key={index} className="flex gap-3">
                  <Skeleton className="h-16 w-9" />
                  <div className="flex flex-1 flex-col gap-2">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                </div>
              ))}
            </SkeletonGroup>
          ) : (
            <VersionHistoryList
              versions={versions}
              viewingId={state === 'viewing' ? (viewingId ?? 'v10') : null}
              restoringId={restoringId}
              onView={(id) => {
                setViewingId(id);
                setState('viewing');
              }}
              onRestore={restore}
              onToggleBookmark={(id) => setVersions(versions.map((version) => (version.id === id ? { ...version, bookmarked: !version.bookmarked } : version)))}
              onRename={(id, name) => setVersions(versions.map((version) => (version.id === id ? { ...version, name } : version)))}
            />
          )}
        </aside>
      </div>
      <Dialog
        open={state === 'conflict'}
        onOpenChange={(open) => !open && setState('list')}
        role="alertdialog"
        title="Undo “Trimmed silences, added captions”?"
        description="You made 2 hand edits after it: “Moved the title down” and “Changed caption colour”. Undoing now also removes them. Both stay in version history."
        footer={
          <>
            <Button variant="secondary" data-autofocus onClick={() => setState('list')}>
              Keep everything
            </Button>
            <Button onClick={() => setState('list')}>Undo all three</Button>
          </>
        }
      />
    </ScreenShell>
  );
}
