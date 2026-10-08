'use client';

import { CalendarClock, Download, Link2 } from 'lucide-react';
import { useState } from 'react';

import { Button, Dialog, Disclosure, RenderCard, type RenderStatus, SegmentedControl, Switch, useToast } from '@/components/ui';

import { PROJECT } from '../_components/sample';
import { ScreenShell, StateSwitcher } from '../_components/ScreenShell';

const STATES: ReadonlyArray<{ value: RenderStatus; label: string }> = [
  { value: 'queued', label: 'Queued' },
  { value: 'rendering', label: 'Rendering' },
  { value: 'checking', label: 'Checking' },
  { value: 'done', label: 'Ready' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'expired', label: 'Expired' },
];

const META = '0:44 · 1080×1920 · MP4 · ≈ 38 MB';

/** Export as a job (editor §11): the dialog that starts it, then the render card in every state. */
export function ExportShare() {
  const [state, setState] = useState<RenderStatus>('rendering');
  return (
    <ScreenShell
      title="Export and share"
      summary="Export dialog (⌘E) and the render card: queued, rendering with a real percentage, checking, a verified Ready, failed, cancelled, expired."
      flags={['new_ui_export']}
      controls={<StateSwitcher label="Render card" options={STATES} value={state} onChange={(value) => setState(value as RenderStatus)} />}
    >
      <ExportDemo state={state} onStateChange={setState} />
    </ScreenShell>
  );
}

/** Inside ScreenShell, so toasts have their provider. */
function ExportDemo({ state, onStateChange: setState }: { state: RenderStatus; onStateChange: (state: RenderStatus) => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [quality, setQuality] = useState('1080');
  const [blocking, setBlocking] = useState(false);

  const exportNow = () => {
    setOpen(false);
    setState('queued');
  };

  return (
    <>
      <div className="mx-auto flex w-full max-w-xl flex-col gap-6">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="secondary" leadingIcon={<Download />} onClick={() => setOpen(true)}>
            Export
          </Button>
          <Switch label="Blocking endpoint (until EB-24)" checked={blocking} onCheckedChange={setBlocking} />
        </div>

        <RenderCard
          title="Why ₹499 works"
          meta={META}
          status={state}
          step="Burning in captions"
          percent={state === 'rendering' && !blocking ? 58 : undefined}
          eta={state === 'rendering' && !blocking ? 'about 0:40 left' : undefined}
          queuePosition={2}
          keepTabOpen={blocking}
          facts={['Watermark on', 'Channel intro first']}
          downloadPrimary
          onDownload={() => toast.show({ title: 'Downloading why-499-works.mp4' })}
          actions={
            <>
              <Button size="sm" variant="ghost" leadingIcon={<Link2 />} onClick={() => toast.show({ title: 'Link copied' })}>
                Copy link
              </Button>
              <Button size="sm" variant="ghost" leadingIcon={<CalendarClock />}>
                Schedule
              </Button>
            </>
          }
          onCancel={() => setState('cancelled')}
          onRetry={() => setState('queued')}
        />
      </div>

      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Export"
        description={`${PROJECT.title} · 0:44 · 9:16`}
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={exportNow}>Export video</Button>
          </>
        }
      >
        <div className="flex flex-col gap-5">
          <p className="text-cn-label text-cn-fg-secondary">Video file</p>
          <SegmentedControl
            label="Quality"
            value={quality}
            onValueChange={setQuality}
            options={[
              { value: '1080', label: '1080p' },
              { value: '720', label: '720p · faster' },
              { value: '4k', label: '4K', disabled: true, ariaLabel: '4K, on Pro' },
            ]}
          />
          <div className="flex flex-col gap-3">
            <Switch label="Title text" description="The headline at the top of the video" defaultChecked />
            <Switch label="Clipnera watermark" description="Paid plans can turn it off" checked disabled />
            <Switch label="Channel intro" description="Plays before the clip" />
            <Switch label="Captions burned in" defaultChecked />
          </div>
          <Disclosure title="Advanced" summary="MP4 · same frame rate as source">
            <p className="text-cn-label text-cn-fg-secondary">Format MP4. Frame rate: same as source, 30 or 60. Also make one ZIP of every clip.</p>
          </Disclosure>
          <p className="font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">1 file · about 38 MB</p>
        </div>
      </Dialog>
    </>
  );
}
