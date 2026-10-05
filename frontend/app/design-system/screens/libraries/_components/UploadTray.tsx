'use client';

import { ChevronDown, ChevronUp, CircleCheck, CircleAlert, Copy, Pause, Play, ShieldAlert, X } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { IconButton } from '@/components/ui/IconButton';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { WorkingText } from '@/components/ui/WorkingText';
import { cx } from '@/lib/design/styles';

export type TrayRowState =
  | 'checking'
  | 'duplicate'
  | 'too-big'
  | 'over-quota'
  | 'uploading'
  | 'paused'
  | 'needs-file'
  | 'processing'
  | 'ready'
  | 'held'
  | 'failed';

export interface TrayRow {
  id: string;
  name: string;
  size: string;
  state: TrayRowState;
  progress?: number;
  speed?: string;
  left?: string;
  step?: string;
  shots?: number;
}

/** Every row state from 05 §3.3, one of each, for the "all states" mockup. */
export const ALL_TRAY_ROWS: TrayRow[] = [
  { id: 'r1', name: 'beach-run.mov', size: '412 MB', state: 'uploading', progress: 62, speed: '8.4 MB/s', left: '19 s left' },
  { id: 'r2', name: 'office-wide.mp4', size: '1.1 GB', state: 'processing', step: 'Finding shots' },
  { id: 'r3', name: 'bottle-turntable.mp4', size: '188 MB', state: 'ready', shots: 4 },
  { id: 'r4', name: 'cafe.mov', size: '96 MB', state: 'duplicate' },
  { id: 'r5', name: 'rooftop-4k.mov', size: '5.2 GB', state: 'too-big' },
  { id: 'r6', name: 'drone-coast.mp4', size: '2.0 GB', state: 'over-quota' },
  { id: 'r7', name: 'street-night.mp4', size: '640 MB', state: 'paused', progress: 35 },
  { id: 'r8', name: 'interview-b.mov', size: '880 MB', state: 'needs-file', progress: 48 },
  { id: 'r9', name: 'night-drive.mp4', size: '240 MB', state: 'held' },
  { id: 'r10', name: 'screen-recording.mkv', size: '75 MB', state: 'failed' },
  { id: 'r11', name: 'b-roll-park.mp4', size: '210 MB', state: 'checking' },
];

function RowBody({ row }: { row: TrayRow }) {
  switch (row.state) {
    case 'checking':
      return <WorkingText className="text-cn-caption">Checking file</WorkingText>;
    case 'duplicate':
      return <p className="text-cn-caption text-cn-fg-secondary">Already in your library as 'Cafe interior'.</p>;
    case 'too-big':
      return <p className="text-cn-caption text-cn-danger-text">Larger than 4 GB, the most Pro allows for one file.</p>;
    case 'over-quota':
      return <p className="text-cn-caption text-cn-danger-text">Needs 2.0 GB; you have 1.4 GB free.</p>;
    case 'uploading':
      return (
        <div className="space-y-1">
          <ProgressBar label={`Uploading ${row.name}`} hideLabel value={row.progress} size="sm" />
          <p className="font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">
            {row.progress}% · {row.speed} · {row.left}
          </p>
        </div>
      );
    case 'paused':
      return (
        <div className="space-y-1">
          <ProgressBar label={`${row.name} paused`} hideLabel value={row.progress} size="sm" />
          <p className="text-cn-caption text-cn-fg-muted">Paused — resumes when you're back online.</p>
        </div>
      );
    case 'needs-file':
      return <p className="text-cn-caption text-cn-fg-secondary">{row.progress}% uploaded. Choose '{row.name}' again to resume.</p>;
    case 'processing':
      return <WorkingText className="text-cn-caption">{row.step ?? 'Preparing preview'}</WorkingText>;
    case 'ready':
      return (
        <p className="inline-flex items-center gap-1 text-cn-caption text-cn-success-text">
          <CircleCheck aria-hidden className="size-3.5" /> Ready · {row.shots} shots
        </p>
      );
    case 'held':
      return (
        <p className="inline-flex items-center gap-1 text-cn-caption text-cn-fg-secondary">
          <ShieldAlert aria-hidden className="size-3.5" /> Held for review. It can't be used until we check it.
        </p>
      );
    case 'failed':
      return (
        <p className="inline-flex items-start gap-1 text-cn-caption text-cn-danger-text">
          <CircleAlert aria-hidden className="mt-px size-3.5 shrink-0" /> I couldn't read this video. Nothing was charged. Try MP4 or MOV.
        </p>
      );
  }
}

function RowActions({ row }: { row: TrayRow }) {
  const remove = <IconButton size="sm" label={`Remove ${row.name}`} icon={<X />} />;
  switch (row.state) {
    case 'checking':
    case 'processing':
      return row.state === 'checking' ? <Button size="sm" variant="ghost">Cancel</Button> : null;
    case 'duplicate':
      return (
        <>
          <Button size="sm" variant="secondary" leadingIcon={<Copy />}>Use existing</Button>
          <Button size="sm" variant="ghost">Upload anyway</Button>
        </>
      );
    case 'too-big':
    case 'over-quota':
      return (
        <>
          <Button size="sm" variant="secondary">{row.state === 'too-big' ? 'Upgrade' : 'Free up space'}</Button>
          {remove}
        </>
      );
    case 'uploading':
      return (
        <>
          <IconButton size="sm" label={`Pause ${row.name}`} icon={<Pause />} />
          {remove}
        </>
      );
    case 'paused':
      return (
        <>
          <IconButton size="sm" label={`Resume ${row.name}`} icon={<Play />} />
          {remove}
        </>
      );
    case 'needs-file':
      return (
        <>
          <Button size="sm" variant="secondary">Choose file</Button>
          {remove}
        </>
      );
    case 'ready':
      return <Button size="sm" variant="ghost">Open</Button>;
    case 'held':
      return <Button size="sm" variant="ghost">Learn more</Button>;
    case 'failed':
      return (
        <>
          <Button size="sm" variant="secondary">Try again</Button>
          {remove}
        </>
      );
  }
}

/**
 * Upload tray (05 §3.3). Global, in the shell, survives navigation. Bottom
 * right on desktop (416 px), a full-width sheet above the tab bar on phones.
 * Collapses to its header; the header names the overall state, so the
 * collapsed tray still says what is happening. Row changes are announced
 * once by a polite live region, not by each progress tick.
 */
export function UploadTray({ rows, defaultOpen = true }: { rows: ReadonlyArray<TrayRow>; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const done = rows.filter((r) => r.state === 'ready').length;
  const active = rows.filter((r) => r.state === 'uploading' || r.state === 'processing' || r.state === 'checking').length;
  const needsYou = rows.filter((r) => ['duplicate', 'too-big', 'over-quota', 'needs-file', 'failed'].includes(r.state)).length;

  return (
    <section
      aria-labelledby="upload-tray-title"
      className="fixed inset-x-4 bottom-4 z-cn-banner overflow-hidden rounded-cn-xl border border-cn-border-strong bg-cn-surface-raised shadow-cn-3 sm:inset-x-auto sm:right-6 sm:w-[26rem]"
    >
      <header className="flex items-center gap-2 border-b border-cn-border px-4 py-3">
        <div className="min-w-0 flex-1">
          <h2 id="upload-tray-title" className="text-cn-body font-semibold text-cn-fg">
            Uploads · {done} of {rows.length} ready
          </h2>
          <p className="text-cn-caption text-cn-fg-muted">
            {active > 0 ? `${active} in progress` : 'Nothing in progress'}
            {needsYou > 0 && ` · ${needsYou} need you`}
          </p>
        </div>
        <IconButton
          size="sm"
          label={open ? 'Collapse uploads' : 'Expand uploads'}
          aria-expanded={open}
          aria-controls="upload-tray-list"
          icon={open ? <ChevronDown /> : <ChevronUp />}
          onClick={() => setOpen((o) => !o)}
        />
        <IconButton size="sm" label="Close uploads (keeps them running)" icon={<X />} />
      </header>
      {open && (
        <>
          <ul id="upload-tray-list" className="max-h-96 divide-y divide-cn-border overflow-y-auto">
            {rows.map((row) => (
              <li key={row.id} className="space-y-1.5 px-4 py-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-cn-label font-semibold text-cn-fg">{row.name}</p>
                    <p className="font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">{row.size}</p>
                  </div>
                  <div className={cx('flex shrink-0 items-center gap-1')}>
                    <RowActions row={row} />
                  </div>
                </div>
                <RowBody row={row} />
              </li>
            ))}
          </ul>
          <p className="border-t border-cn-border px-4 py-2 text-cn-caption text-cn-fg-muted">
            Keep this tab open while files upload. Phones may slow uploads in the background.
          </p>
        </>
      )}
      <p className="sr-only" role="status" aria-live="polite">
        bottle-turntable.mp4 is ready with 4 shots.
      </p>
    </section>
  );
}
