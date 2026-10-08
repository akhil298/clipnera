'use client';

import { Captions, Download, FolderOpen, Library, Link2, MessageSquare, Music, Palette, Pencil, Scissors, Trash2, Type, Upload } from 'lucide-react';
import { useState } from 'react';

import {
  ActivityIndicator,
  BrollPick,
  type BrollShot,
  Button,
  CheckInCard,
  CitationChip,
  FloatingToolbar,
  IconButton,
  InlineAlert,
  MediaCard,
  type Moment,
  PromptBar,
  type PromptContext,
  type PromptMode,
  PromptQueue,
  QualityBadge,
  type QueuedPrompt,
  RenderCard,
  SelectionBar,
  SLASH_COMMANDS,
  SourceStrip,
  ToolRailItem,
  useToast,
  VersionItem,
} from '@/components/ui';

import { GallerySection, Specimen, State, StateGrid } from './Specimen';

const SOURCE_CHIP: PromptContext = { id: 'src', kind: 'source', label: 'Kavya on pricing', meta: '52:10' };
const SHOTS: ReadonlyArray<BrollShot> = [
  { id: 'a', title: 'Coffee cup on a desk', source: 'Clipnera library', duration: 5 },
  { id: 'b', title: 'Café counter, Mumbai', source: 'Clipnera library', duration: 8 },
  { id: 'c', title: 'Filter coffee pour', source: 'Your uploads', duration: 4 },
  { id: 'd', title: 'Two cups clinking', source: 'Clipnera library', duration: 6 },
];
const MOMENTS: ReadonlyArray<Moment> = [
  { id: 'm1', quote: 'It found the leak faster than I did.', start: 2630, duration: 13, tag: 'Hot take', score: 94 },
  { id: 'm2', quote: 'We tried ₹999 first and nobody converted.', start: 134, duration: 44, tag: 'Story' },
  { id: 'm3', quote: 'People actually stay for a year.', start: 430, duration: 36, tag: 'Proof', pending: true },
  { id: 'm4', quote: 'Your price is a promise.', start: 541, duration: 39, tag: 'Advice' },
  { id: 'm5', quote: 'Never discount in year one.', start: 612, duration: 32, tag: 'Advice' },
];
const QUEUE: QueuedPrompt[] = [
  { id: 'q1', prompt: 'Add calm music under my voice', chips: [] },
  { id: 'q2', prompt: 'Make the hook shorter', chips: [{ id: 'c', kind: 'range', label: '0:00 – 0:03' }] },
];
const TOOLS = [
  { id: 'captions', label: 'Captions', icon: <Captions />, shortcut: '2' },
  { id: 'type', label: 'Hook', icon: <Type />, shortcut: '3' },
  { id: 'broll', label: 'B-roll', icon: <Library />, shortcut: '4', badge: '2 new cutaways' },
  { id: 'music', label: 'Music', icon: <Music />, shortcut: '5' },
];

function AttachMenu({ close }: { close: () => void }) {
  const rows = [
    { label: 'Upload video', icon: <Upload /> },
    { label: 'Paste link', icon: <Link2 /> },
    { label: 'From library', icon: <FolderOpen /> },
    { label: 'Brand kit', icon: <Palette /> },
  ];
  return (
    <ul className="flex flex-col">
      {rows.map((row) => (
        <li key={row.label}>
          <Button variant="ghost" size="sm" fullWidth leadingIcon={row.icon} onClick={close} className="justify-start">
            {row.label}
          </Button>
        </li>
      ))}
    </ul>
  );
}

/** DS-E editor primitives (screens/02-editor §19.1), in their states. */
export function EditorSection() {
  const toast = useToast();
  const [hero, setHero] = useState('');
  const [docked, setDocked] = useState('');
  const [mode, setMode] = useState<PromptMode>('edit');
  const [queue, setQueue] = useState(QUEUE);
  const [tool, setTool] = useState('broll');
  const [selected, setSelected] = useState(3);

  return (
    <GallerySection id="editor" title="Editor primitives" intro="Composer upgrades and the editor's building blocks (DS-E). Presentational; the parent owns state.">
      <Specimen title="PromptBar: hero and docked" note="Hero: 24 px radius, raised, no mode pill, sends with only a source chip. Docked: mode pill, / opens commands, + anchors a popover, files drop on the box.">
        <div className="space-y-6">
          <State label="hero · source chip · drop a file · + popover" className="items-stretch">
            <PromptBar
              size="hero"
              value={hero}
              onValueChange={setHero}
              onSubmit={() => toast.show({ title: 'Sent', description: hero || 'Source only' })}
              contexts={[SOURCE_CHIP]}
              onRemoveContext={() => undefined}
              attachMenu={(close) => <AttachMenu close={close} />}
              onDropFile={(files) => toast.show({ title: `Dropped ${files.length} file${files.length === 1 ? '' : 's'}` })}
              creditCost={52}
            />
          </State>
          <div className="grid gap-6 md:grid-cols-2">
            <State label="docked · type / for commands" className="items-stretch">
              <div className="pt-64">
                <PromptBar value={docked} onValueChange={setDocked} onSubmit={() => setDocked('')} mode={mode} onModeChange={setMode} slashCommands={SLASH_COMMANDS} creditCost={mode === 'edit' && docked ? 4 : undefined} hint={mode === 'ask' ? 'Free · 17 of 20 left today' : undefined} />
              </div>
            </State>
            <State label="running, empty field (Stop) · not sent footer" className="items-stretch">
              <PromptBar
                value=""
                onValueChange={() => undefined}
                onSubmit={() => undefined}
                running
                onStop={() => toast.show({ title: 'Stopping at the next safe point' })}
                footer={
                  <InlineAlert tone="danger" live="alert" action={<Button size="sm" variant="secondary">Retry</Button>}>
                    Not sent. Check your connection.
                  </InlineAlert>
                }
              />
            </State>
            <State label="offline (reason in the Send tooltip)" className="items-stretch">
              <PromptBar value="Trim the silences" onValueChange={() => undefined} onSubmit={() => undefined} disabledReason="You’re offline. Your prompt is kept." />
            </State>
          </div>
        </div>
      </Specimen>

      <Specimen title="CitationChip and SourceStrip" note="Timecodes, not numbers. Hover or focus previews; click seeks; Shift-click adds the range to the prompt.">
        <div className="space-y-4">
          <p className="max-w-xl text-cn-prose text-cn-fg-secondary">
            The strongest line is at
            <CitationChip citation={{ start: 724, end: 751, quote: 'If you can’t explain the price, you haven’t finished the product.' }} onSeek={(s) => toast.show({ title: `Seek to ${s}s` })} onAttach={() => toast.show({ title: 'Range added to the prompt' })} />
            and the story lands at
            <CitationChip citation={{ start: 1865 }} more={2} onSeek={() => undefined} />.
          </p>
          <SourceStrip moments={MOMENTS} onSeek={(m) => toast.show({ title: `Seek to ${m.start}s` })} onUse={(m) => toast.show({ title: `Added “${m.quote}”` })} />
        </div>
      </Specimen>

      <Specimen title="CheckInCard and PromptQueue">
        <div className="grid gap-4 md:grid-cols-2">
          <CheckInCard checkIn={{ reason: 'approval', credits: { estimate: 84, spent: 0 }, approval: { text: 'This removes 54% of the clip.' }, options: ['continue', 'finish'] }} onDecide={(d) => toast.show({ title: d })} />
          <CheckInCard checkIn={{ reason: 'credits', credits: { estimate: 30, spent: 18 }, needed: 12, options: ['add_credits', 'finish'], decided: 'finish' }} onDecide={() => undefined} />
          <PromptQueue items={queue} onChange={setQueue} className="md:col-span-2" />
        </div>
      </Specimen>

      <Specimen title="RenderCard" note="Real percentage or none; Download is secondary unless it is the view's one action.">
        <div className="grid gap-3 md:grid-cols-2">
          <RenderCard title="Opening hook" meta="0:42 · 1080×1920 · MP4" status="queued" queuePosition={2} onCancel={() => undefined} />
          <RenderCard title="Opening hook" meta="0:42 · 1080×1920 · MP4" status="rendering" step="Burning in captions" percent={58} eta="about 0:40 left" onCancel={() => undefined} />
          <RenderCard title="Opening hook" meta="0:42 · 1080×1920 · MP4 · 38 MB" status="done" facts={['Watermark on']} onDownload={() => undefined} />
          <RenderCard title="Opening hook" status="failed" onRetry={() => undefined} />
        </div>
      </Specimen>

      <Specimen title="MediaCard and BrollPick" note="Chromeless tile with the media hairline; duration on the poster, meta below.">
        <div className="space-y-4">
          <div className="grid max-w-md grid-cols-2 gap-3 sm:grid-cols-4">
            {SHOTS.map((shot, index) => (
              <MediaCard key={shot.id} size="sm" title={shot.title} meta={shot.source} duration={shot.duration} selected={index === 0} />
            ))}
          </div>
          <BrollPick shot={SHOTS[2]} range="0:12–0:16" reasons={['matches “coffee” and “pour”', 'fits 9:16']} alternates={SHOTS} onSwap={(s) => toast.show({ title: `Swapped to ${s.title}` })} onUndo={() => undefined} onSearchElse={() => undefined} />
        </div>
      </Specimen>

      <Specimen title="VersionItem">
        <ol className="flex max-w-md flex-col gap-1">
          <VersionItem version={{ id: 'v12', name: 'Trimmed silences', author: 'Clipnera', time: 'Just now', exactTime: '5 Oct 2026, 14:05', current: true }} onView={() => undefined} onRestore={() => undefined} onToggleBookmark={() => undefined} onRename={() => undefined} />
          <VersionItem version={{ id: 'v10', name: 'Added B-roll at 0:12', author: 'Clipnera', time: '22 min ago', exactTime: '5 Oct 2026, 13:43', bookmarked: true, exported: true }} viewing onView={() => undefined} onRestore={() => undefined} onToggleBookmark={() => undefined} onRename={() => undefined} onCompare={() => undefined} />
          <VersionItem version={{ id: 'v9', name: 'Restored “First cut”', author: 'You', time: '1 hour ago', exactTime: '5 Oct 2026, 13:01', restored: true }} restoring onView={() => undefined} onRestore={() => undefined} onToggleBookmark={() => undefined} onRename={() => undefined} />
        </ol>
      </Specimen>

      <Specimen title="Stage chrome: QualityBadge, FloatingToolbar" note="Always dark on the stage. Drag the grip (or arrow keys on it) to a corner.">
        <div className="relative h-72 overflow-hidden rounded-cn-lg bg-cn-stage">
          <QualityBadge visible className="absolute left-3 top-3" />
          <div className="absolute left-1/3 top-1/2 h-10 w-40 rounded-cn-xs outline outline-2 outline-cn-accent" />
          <FloatingToolbar label="Caption actions" anchor={{ top: 144, left: 192, width: 160, height: 40 }} onDismiss={() => undefined}>
            <IconButton size="sm" label="Ask about this" icon={<MessageSquare />} />
            <IconButton size="sm" label="Edit words" icon={<Pencil />} />
            <IconButton size="sm" label="Hide this line" icon={<Scissors />} />
          </FloatingToolbar>
        </div>
      </Specimen>

      <Specimen title="ToolRailItem, ActivityIndicator, SelectionBar">
        <StateGrid>
          <State label="rail">
            <nav aria-label="Tools" className="flex flex-col gap-1 rounded-cn-lg bg-cn-surface p-1">
              {TOOLS.map((item) => (
                <ToolRailItem key={item.id} {...item} active={tool === item.id} onClick={() => setTool(tool === item.id ? '' : item.id)} />
              ))}
            </nav>
          </State>
          <State label="activity pill">
            <ActivityIndicator
              items={[
                { id: 'a', title: 'Kavya on pricing', step: 'Making the full-quality preview' },
                { id: 'b', title: 'Founders Q&A', step: 'Exporting 3 clips', percent: 42 },
              ]}
            />
          </State>
          <State label="selection (inline)" className="col-span-2">
            <SelectionBar count={selected} noun="clip" placement="inline" onSelectAll={() => setSelected(12)} onClear={() => setSelected(0)}>
              <Button size="sm" variant="secondary" leadingIcon={<Download />}>
                Download
              </Button>
              <Button size="sm" variant="ghost" leadingIcon={<Trash2 />}>
                Delete
              </Button>
            </SelectionBar>
            {selected === 0 && (
              <Button size="sm" variant="secondary" onClick={() => setSelected(3)}>
                Select 3 again
              </Button>
            )}
          </State>
        </StateGrid>
      </Specimen>
    </GallerySection>
  );
}
