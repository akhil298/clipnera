'use client';

import { ChevronDown, CircleAlert, CloudUpload, Folder, Link2, Lock, Sparkles, X } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Checkbox } from '@/components/ui/Checkbox';
import { Chip } from '@/components/ui/Chip';
import { Dialog } from '@/components/ui/Dialog';
import { IconButton } from '@/components/ui/IconButton';
import { Input } from '@/components/ui/Input';
import { Menu } from '@/components/ui/Menu';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Skeleton } from '@/components/ui/Skeleton';
import { Switch } from '@/components/ui/Switch';
import { Textarea } from '@/components/ui/Textarea';
import { WorkingText } from '@/components/ui/WorkingText';
import { cx, focusRing } from '@/lib/design/styles';

import { AppShell } from '../_mock/AppShell';
import { folders } from '../_mock/data';
import { ScreenFrame } from '../_mock/ScreenFrame';
import { Poster, SourceChip } from '../_mock/StandIns';
import { SCREENS } from '../_mock/states';

const FORMATS = [
  { value: '9:16', label: '9:16 vertical', note: 'Shorts, Reels' },
  { value: '4:5', label: '4:5 portrait', note: 'Instagram feed' },
  { value: '1:1', label: '1:1 square', note: 'Feeds' },
  { value: '16:9', label: '16:9 landscape', note: 'YouTube, web' },
] as const;

const STRENGTH = [
  { value: 'light', label: 'Light' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'maximum', label: 'Maximum' },
] as const;

const SCRIPT = [
  { value: 'auto', label: 'Auto' },
  { value: 'roman', label: 'Roman' },
  { value: 'native', label: 'Native' },
] as const;

export function UploadMock({ state, theme }: { state: string; theme?: string }) {
  const [open, setOpen] = useState(true);
  const [optionsOpen, setOptionsOpen] = useState(state === 'options');
  const [formats, setFormats] = useState<string[]>(['9:16']);
  const [folder, setFolder] = useState(folders[0].name);
  const [nudge, setNudge] = useState(state === 'file');
  const isFile = state === 'file' || state === 'too-long';
  const noCredits = state === 'no-credits';
  const blocked = noCredits || state === 'too-long' || state === 'drop' || state === 'checking';
  const extra = Math.max(formats.length - 1, 0);
  const cost = Math.round(116 * (1 + 0.5 * extra));

  const toggleFormat = (value: string) =>
    setFormats((current) => (current.includes(value) ? (current.length > 1 ? current.filter((v) => v !== value) : current) : [...current, value]));

  return (
    <ScreenFrame
      screen={SCREENS.upload.title}
      states={SCREENS.upload.states}
      state={state}
      theme={theme}
      note="Opens from Home’s send, New video, the tab bar + and empty states. It is an intercepted route (/dashboard/upload), so Back closes it and a link can open it."
    >
      <AppShell active="home" crumbs={[{ label: 'Home' }]} hidePromptEntry>
        <div className="mx-auto max-w-3xl py-16 text-center">
          <h1 className="text-cn-display-sm font-bold">What should we cut today?</h1>
          <Button className="mt-6" onClick={() => setOpen(true)}>
            Open New video
          </Button>
        </div>

        <Dialog
          open={open}
          onOpenChange={setOpen}
          size="lg"
          title="New video"
          description="Check the video and the cost. I start once you confirm, and you can close the tab after any upload finishes."
          dismissible={state !== 'starting'}
          footer={
            <div className="flex w-full flex-col gap-3 sm:flex-row sm:items-center">
              <p className="flex-1 text-cn-label text-cn-fg-secondary">
                {state === 'checking' || state === 'drop' ? (
                  'Choose a video to see the cost'
                ) : (
                  <>
                    {formats.length} format{formats.length === 1 ? '' : 's'}
                    {!noCredits && state !== 'too-long' && (
                      <>
                        {' · '}
                        <span className="font-cn-mono tabular-nums">{(1240 - cost).toLocaleString('en-IN')}</span> credits left after
                      </>
                    )}
                  </>
                )}
              </p>
              <Button variant="ghost" className="hidden sm:inline-flex" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button disabled={blocked} loading={state === 'starting'} loadingLabel="Starting" leadingIcon={<Sparkles />}>
                Make clips{blocked || state === 'too-long' ? '' : ` · ${cost} credits`}
              </Button>
            </div>
          }
        >
          <div className="flex flex-col gap-5">
            {nudge && (
              <div className="flex items-start gap-3 rounded-cn-md border border-cn-border bg-cn-surface p-3">
                <p className="flex-1 text-cn-label text-cn-fg-secondary">
                  Add your channel intro first? It plays once at the start of each export on Pro.
                </p>
                <Button size="sm" variant="ghost">
                  Create intro
                </Button>
                <IconButton label="Not now" icon={<X />} size="sm" onClick={() => setNudge(false)} />
              </div>
            )}

            <section aria-labelledby="up-source" className="flex flex-col gap-2">
              <h3 id="up-source" className="text-cn-label font-semibold">
                Video
              </h3>
              {state === 'drop' ? (
                <div className="flex flex-col gap-3">
                  <div className="flex flex-col items-center gap-2 rounded-cn-lg border border-dashed border-cn-control-border bg-cn-field px-4 py-8 text-center">
                    <CloudUpload aria-hidden className="size-6 text-cn-fg-secondary" />
                    <p className="text-cn-body text-cn-fg">Drop a video here</p>
                    <p className="text-cn-caption text-cn-fg-muted">MP4, MOV, WebM or MKV · up to 2 hours on your plan</p>
                    <Button size="sm" variant="secondary" className="mt-1">
                      Choose a file
                    </Button>
                  </div>
                  <Input label="Or paste a YouTube link" leading={<Link2 />} placeholder="youtube.com/watch?v=…" />
                </div>
              ) : state === 'checking' ? (
                <div className="flex items-center gap-3 rounded-cn-lg border border-cn-border bg-cn-surface p-3">
                  <Skeleton className="h-14 w-24 shrink-0" />
                  <div className="flex flex-1 flex-col gap-1.5">
                    <WorkingText className="text-cn-label">Checking the link</WorkingText>
                    <span className="truncate font-cn-mono text-cn-caption text-cn-fg-muted">youtube.com/watch?v=Qm3x…</span>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-3 rounded-cn-lg border border-cn-border bg-cn-surface p-3">
                  <Poster duration={isFile ? (state === 'too-long' ? '2:41:00' : '1:12:40') : '58:12'} className="w-28 shrink-0" />
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    {isFile ? (
                      <SourceChip kind="file" title="masterclass-final.mp4" meta="1.9 GB" />
                    ) : (
                      <SourceChip kind="youtube" title="Episode 41 — Why we stopped chasing views" meta="Founder Podcast" />
                    )}
                    <span className="text-cn-caption text-cn-fg-muted">{isFile ? 'Uploads from this tab, then continues on our side' : 'Link checked · 1080p'}</span>
                  </div>
                  <Button size="sm" variant="ghost">
                    Change
                  </Button>
                </div>
              )}
              {state === 'too-long' && (
                <p role="alert" className="flex flex-wrap items-center gap-2 text-cn-label text-cn-danger-text">
                  <CircleAlert aria-hidden className="size-4" />
                  This video is 2 h 41 min. Your plan takes up to 2 hours per video.
                  <Button size="sm" variant="ghost">
                    See plans
                  </Button>
                </p>
              )}
            </section>

            <Textarea
              label="What should Clipnera make?"
              hint="Optional. Leave it empty and I pick the best moments."
              defaultValue="Find the 5 best moments, under 45 seconds, Hinglish captions"
              minRows={2}
              maxRows={5}
              maxLength={500}
            />

            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                label="Project name"
                defaultValue={isFile ? 'Masterclass: pricing your first product' : 'Episode 41 — Why we stopped chasing views'}
                hint="Filled from the video; change it any time."
              />
              <div className="flex flex-col gap-1.5">
                <span id="up-folder" className="text-cn-label font-semibold">
                  Folder
                </span>
                <Menu
                  items={[
                    { id: 'none', label: 'No folder', checked: folder === 'No folder', onSelect: () => setFolder('No folder') },
                    { type: 'separator', id: 's' },
                    ...folders.map((f) => ({ id: f.id, label: f.name, checked: folder === f.name, onSelect: () => setFolder(f.name) })),
                    { type: 'separator', id: 's2' },
                    { id: 'new', label: 'New folder…', onSelect: () => undefined },
                  ]}
                  trigger={(props) => (
                    <button
                      type="button"
                      {...props}
                      aria-labelledby={`up-folder ${props.id}`}
                      className={cx(
                        'flex h-9 items-center gap-2 rounded-cn-md border border-cn-control-border bg-cn-field px-3 text-left text-cn-body text-cn-fg hover:border-cn-fg-muted',
                        focusRing,
                      )}
                    >
                      <Folder aria-hidden className="size-4 text-cn-fg-muted" />
                      <span className="flex-1 truncate">{folder}</span>
                      <ChevronDown aria-hidden className="size-4 text-cn-fg-muted" />
                    </button>
                  )}
                />
              </div>
            </div>

            <section aria-labelledby="up-options" className="rounded-cn-lg border border-cn-border">
              <h3 id="up-options">
                <button
                  type="button"
                  aria-expanded={optionsOpen}
                  aria-controls="up-options-panel"
                  onClick={() => setOptionsOpen(!optionsOpen)}
                  className={cx('flex w-full items-center gap-3 rounded-cn-lg px-3 py-2.5 text-left', focusRing)}
                >
                  <span className="text-cn-label font-semibold text-cn-fg">Options</span>
                  <span className="min-w-0 flex-1 truncate text-cn-label text-cn-fg-muted">{formats.join(', ')} · Studio voice, Maximum · Captions auto</span>
                  <ChevronDown aria-hidden className={cx('size-4 text-cn-fg-muted motion-safe:transition-transform motion-safe:duration-cn-base', optionsOpen && 'rotate-180')} />
                </button>
              </h3>
              {optionsOpen && (
                <div id="up-options-panel" className="flex flex-col gap-5 border-t border-cn-border p-3">
                  <fieldset className="flex flex-col gap-2">
                    <legend className="mb-2 text-cn-label font-semibold">Formats</legend>
                    <div className="flex flex-wrap gap-2">
                      {FORMATS.map((format) => (
                        <Chip key={format.value} selected={formats.includes(format.value)} onClick={() => toggleFormat(format.value)}>
                          {format.label}
                        </Chip>
                      ))}
                      <Chip disabled icon={<Lock />}>
                        More formats with Pro
                      </Chip>
                    </div>
                    <p className="text-cn-caption text-cn-fg-muted">The first format is included; each extra one adds half the cost.</p>
                  </fieldset>
                  <div className="flex flex-col gap-3">
                    <Switch label="Studio voice" description="Removes room echo, mic hiss, fan hum and background noise." defaultChecked />
                    <div className="flex flex-wrap items-center gap-3 pl-1">
                      <span className="text-cn-label text-cn-fg-secondary">
                        Strength
                      </span>
                      <SegmentedControl label="Studio voice strength" size="sm" options={STRENGTH} defaultValue="maximum" />
                    </div>
                    <div className="grid gap-2 sm:grid-cols-3">
                      <Checkbox label="Remove echo" defaultChecked />
                      <Checkbox label="Voice clarity" defaultChecked />
                      <Checkbox label="50/60 Hz hum filter" defaultChecked />
                    </div>
                  </div>
                  <div className="flex flex-col gap-3">
                    <Switch label="B-roll cutaways" description="Adds matching footage where it fits. 5 credits per clip that gets B-roll." />
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="text-cn-label text-cn-fg-secondary">Hindi and Telugu captions</span>
                      <SegmentedControl label="Caption script" size="sm" options={SCRIPT} defaultValue="auto" />
                      <span className="text-cn-caption text-cn-fg-muted">Auto writes Hinglish and Tenglish in Roman letters.</span>
                    </div>
                  </div>
                </div>
              )}
            </section>

            {noCredits && (
              <div role="alert" className="flex flex-wrap items-center gap-3 rounded-cn-md border border-cn-danger/30 bg-cn-danger-subtle p-3">
                <p className="flex-1 text-cn-label text-cn-danger-text">This video needs 116 credits; you have 6. Pick fewer formats, or add credits and come back.</p>
                <Button size="sm" variant="secondary">
                  Add credits
                </Button>
              </div>
            )}
            {state === 'error' && (
              <div role="alert" className="flex flex-wrap items-center gap-3 rounded-cn-md border border-cn-danger/30 bg-cn-danger-subtle p-3">
                <p className="flex-1 text-cn-label text-cn-danger-text">I couldn’t start this project. Nothing was charged. Try again in a moment.</p>
              </div>
            )}
            {state === 'starting' && (
              <p role="status" className="text-cn-label text-cn-fg-secondary">
                Creating the project. I’ll take you to its progress page.
              </p>
            )}
            {isFile && (
              <Card padding="sm" className="flex items-center gap-2 text-cn-caption text-cn-fg-muted">
                <Badge tone="info">Upload</Badge>
                Large files upload in parts and resume if the connection drops.
              </Card>
            )}
          </div>
        </Dialog>
      </AppShell>
    </ScreenFrame>
  );
}
