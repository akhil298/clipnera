'use client';

import { ChevronUp, MessageSquare, RotateCcw, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/Button';
import type { PromptContext } from '@/components/ui/ContextChip';
import { Drawer } from '@/components/ui/Drawer';
import { IconButton } from '@/components/ui/IconButton';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { useToast } from '@/components/ui/Toast';
import { WorkingText } from '@/components/ui/WorkingText';
import { cx, focusRing } from '@/lib/design/styles';

import { ConversationPanel } from '../_components/Conversation';
import { EditorTopBar } from '../_components/EditorTopBar';
import { PreviewPlayer } from '../_components/PreviewPlayer';
import { type Speed, useRunSimulator } from '../_components/run/useRunSimulator';
import { SCENARIOS } from '../_components/run/scenarios';
import { CHIP_CLIP, CLIP, type TimelineBlock, VERSIONS } from '../_components/sample';
import { type Device, DeviceFrame, DEVICES, ScreenShell, StateSwitcher } from '../_components/ScreenShell';
import { ShortcutsDialog } from '../_components/ShortcutsDialog';
import { ToolPanel, ToolRail, type Tool } from '../_components/SidePanel';
import { blocksAt, Timeline } from '../_components/Timeline';
import { VersionHistoryList } from '../_components/VersionHistory';

const STATES = [
  { value: 'live', label: 'Live' },
  { value: 'loading', label: 'Loading' },
  { value: 'viewing', label: 'Viewing an earlier version' },
  { value: 'compare', label: 'Compare side by side' },
  { value: 'preview-error', label: 'Preview can’t play' },
];

const SPEEDS = [
  { value: '0.5', label: '0.5×' },
  { value: '1', label: '1×' },
  { value: '2', label: '2×' },
];

const JOBS = [
  { id: 'j1', title: 'Kavya on pricing', step: 'Making the full-quality preview' },
  { id: 'j2', title: 'Founders Q&A', step: 'Exporting 3 clips', percent: 42 },
];

const isField = (target: EventTarget | null) =>
  target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.getAttribute('role') === 'option');

export function Workspace() {
  const toast = useToast();
  const sim = useRunSimulator(40);
  const [device, setDevice] = useState<Device>('desktop');
  const [scenario, setScenario] = useState('happy');
  const [view, setView] = useState('live');
  const [tool, setTool] = useState<Tool | null>('transcript');
  const [time, setTime] = useState(4);
  const [playing, setPlaying] = useState(false);
  const [contexts, setContexts] = useState<PromptContext[]>([CHIP_CLIP]);
  const [selected, setSelected] = useState<string | null>(null);
  const [history, setHistory] = useState(false);
  const [shortcuts, setShortcuts] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [versions, setVersions] = useState(VERSIONS);
  const [viewingId, setViewingId] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const promptRef = useRef<HTMLTextAreaElement>(null);

  const blocks = blocksAt(sim.editor.revision);
  const length = Math.max(...blocks.filter((block) => block.lane === 'video' && !block.cut).map((block) => block.end));
  const captions = blocks.some((block) => block.lane === 'captions');
  const broll = blocks.some((block) => block.lane === 'broll' && time >= block.start && time < block.end);
  const lastTurn = sim.turns[sim.turns.length - 1];

  // Proxy playback stand-in: a clock that is not tied to any media.
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setTime((now) => (now + 0.1 >= length ? 0 : now + 0.1)), 100);
    return () => clearInterval(id);
  }, [playing, length]);

  useEffect(() => setTime((now) => Math.min(now, length)), [length]);

  const focusPrompt = useCallback(() => {
    if (device === 'phone') setSheet(true);
    requestAnimationFrame(() => promptRef.current?.focus());
  }, [device]);

  // Global keys: ⌘K and / focus the prompt; the studio's single keys work outside fields.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const mod = event.metaKey || event.ctrlKey;
      if (mod && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        return focusPrompt();
      }
      if (mod && event.key === '.') {
        event.preventDefault();
        return sim.stop();
      }
      if (mod && event.key.toLowerCase() === 'e') {
        event.preventDefault();
        return toast.show({ title: 'Opens the export dialog', description: 'See the Export & share mockup.' });
      }
      if (mod && event.shiftKey && event.key.toLowerCase() === 'h') {
        event.preventDefault();
        return setHistory(true);
      }
      if (isField(event.target) || mod || event.altKey) return;
      if (event.key === '/') {
        event.preventDefault();
        return focusPrompt();
      }
      if (event.key === ' ' || event.key.toLowerCase() === 'k') {
        if (event.target instanceof HTMLButtonElement) return;
        event.preventDefault();
        setPlaying((value) => !value);
      } else if (event.key.toLowerCase() === 'j') setTime((now) => Math.max(0, now - 2));
      else if (event.key.toLowerCase() === 'l') setTime((now) => Math.min(length, now + 2));
      else if (event.key === '?') setShortcuts(true);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [focusPrompt, length, sim, toast]);

  const replay = () => {
    setView('live');
    setTime(4);
    setContexts([CHIP_CLIP]);
    sim.start(scenario);
  };

  const undoLatest = () => {
    const turn = [...sim.turns].reverse().find((candidate) => candidate.result?.version || candidate.failure?.version);
    if (!turn) return toast.show({ title: 'Nothing to undo yet' });
    sim.undo(turn.id, !turn.undone);
    toast.show({ title: turn.undone ? 'Redone' : `Undone: ${turn.result?.version?.name ?? turn.failure?.version?.name}`, action: { label: turn.undone ? 'Undo' : 'Redo', onClick: () => sim.undo(turn.id, turn.undone) } });
  };

  const onSelectBlock = (block: TimelineBlock | null) => {
    setSelected(block?.id ?? null);
    if (!block) return setContexts([CHIP_CLIP]);
    const chip: PromptContext =
      block.lane === 'captions'
        ? { id: `cap-${block.id}`, kind: 'caption', label: `“${block.label}”` }
        : block.lane === 'video' || block.lane === 'broll'
          ? { id: `clip-${block.id}`, kind: 'clip', label: block.label, meta: `${Math.round(block.end - block.start)}s` }
          : { id: `range-${block.id}`, kind: 'range', label: `0:${String(Math.floor(block.start)).padStart(2, '0')} – 0:${String(Math.floor(block.end)).padStart(2, '0')}` };
    setContexts([chip]);
  };

  const viewing = view === 'viewing' || viewingId ? (versions.find((version) => version.id === (viewingId ?? 'v11')) ?? null) : null;
  const before = { captions: false, title: 'Why ₹499 works', broll: false, name: 'Moved the title down · v11' };

  const player = (compact: boolean) => (
    <PreviewPlayer
      time={time}
      length={length}
      playing={playing}
      onPlayPause={() => setPlaying(!playing)}
      onSeek={setTime}
      quality={sim.editor.quality}
      captions={viewing ? false : captions}
      title={time < 5 ? (sim.editor.revision >= 43 && lastTurn?.prompt.includes('punchier') ? '₹499 beat ₹999. Here’s why.' : 'Why ₹499 works') : null}
      broll={!viewing && broll}
      changedRange={sim.editor.changedRange}
      viewing={
        viewing
          ? {
              name: viewing.name,
              onBack: () => {
                setViewingId(null);
                setView('live');
              },
              onRestore: () => restore(viewing.id),
            }
          : null
      }
      compare={view === 'compare' ? 'side' : 'off'}
      before={sim.turns.some((turn) => turn.result?.version) || view === 'compare' ? before : undefined}
      status={view === 'loading' ? 'loading' : view === 'preview-error' ? 'error' : 'ready'}
      compact={compact}
      className="min-h-0 flex-1"
    />
  );

  const restore = (id: string) => {
    setRestoringId(id);
    setTimeout(() => {
      const source = versions.find((version) => version.id === id);
      setVersions([
        { id: `r${Date.now()}`, name: `Restored “${source?.name}”`, author: 'You', time: 'Just now', exact: 'Now', current: true, kind: 'restore' },
        ...versions.map((version) => ({ ...version, current: false })),
      ]);
      setRestoringId(null);
      setViewingId(null);
      setView('live');
      toast.show({ title: `Restored “${source?.name}”`, description: 'It’s now the newest version. Nothing was deleted.', tone: 'success' });
    }, 900);
  };

  const conversation = (compact: boolean) => (
    <ConversationPanel
      sim={sim}
      contexts={contexts}
      onContextsChange={setContexts}
      promptRef={promptRef}
      onCompare={() => setView(view === 'compare' ? 'live' : 'compare')}
      onSeek={(stamp) => {
        const [m, s] = stamp.split(':').map(Number);
        setTime(m * 60 + s);
      }}
      onOpenLibrary={() => setTool('library')}
      compact={compact}
      className="min-h-0 flex-1"
    />
  );

  const timeline = (compact: boolean) => (
    <Timeline
      revision={sim.editor.revision}
      locked={sim.editor.locked}
      highlight={sim.editor.highlight}
      selectedId={selected}
      onSelect={onSelectBlock}
      playhead={time}
      onSeek={setTime}
      compact={compact}
      className={compact ? 'h-28 shrink-0 border-t border-cn-border' : 'h-60 shrink-0 border-t border-cn-border'}
    />
  );

  const topBar = (compact: boolean) => (
    <EditorTopBar
      versionCount={sim.editor.versionCount}
      versionPulse={sim.editor.versionPulse}
      saveState={sim.editor.online ? 'saved' : 'offline'}
      activity={sim.editor.quality === 'preview' ? JOBS : JOBS.slice(1)}
      balance={sim.editor.balance}
      onHistory={() => setHistory(true)}
      onUndo={undoLatest}
      onRedo={undoLatest}
      onExport={() => toast.show({ title: 'Opens the export dialog', description: 'See the Export & share mockup.' })}
      onShare={() => toast.show({ title: 'Opens the share popover', description: 'See the Export & share mockup.' })}
      onShortcuts={() => setShortcuts(true)}
      compact={compact}
    />
  );

  const controls = (
    <>
      <StateSwitcher label="Device" options={DEVICES} value={device} onChange={(value) => setDevice(value as Device)} />
      <StateSwitcher label="View" options={STATES} value={view} onChange={setView} />
      <StateSwitcher label="Prompt run" options={SCENARIOS.map((item) => ({ value: item.id, label: item.label }))} value={scenario} onChange={setScenario} />
      <div className="flex items-center gap-2">
        <Button size="sm" leadingIcon={<RotateCcw />} onClick={replay}>
          Play this run
        </Button>
        <SegmentedControl label="Replay speed" size="sm" options={SPEEDS} value={String(sim.speed)} onValueChange={(value) => sim.setSpeed(Number(value) as Speed)} />
        <Button size="sm" variant="ghost" onClick={() => sim.reset(40)}>
          Clear
        </Button>
      </div>
      <p className="w-full text-cn-caption text-cn-fg-muted">{SCENARIOS.find((item) => item.id === scenario)?.note} Type while it runs to queue a follow-up. Keys: ⌘K or / prompt, Space play, ? shortcuts.</p>
    </>
  );

  const runLine = lastTurn && !['succeeded', 'partial', 'failed', 'cancelled'].includes(lastTurn.status) ? lastTurn : null;

  return (
    <ScreenShell title="Editor" summary="Conversation, preview, timeline and tools. Replay a prompt run." flags={['new_ui_editor', 'new_ui_editor_timeline', 'prompt_streaming_v2']} controls={controls} bleed>
      <DeviceFrame device={device}>
        {device === 'desktop' && (
          <div className="flex h-[calc(100dvh-170px)] min-h-[560px] flex-col">
            {topBar(false)}
            <div className="flex min-h-0 flex-1">
              <ToolRail tool={tool} onTool={setTool} />
              {tool && (
                <aside aria-label="Tool panel" className="flex w-80 shrink-0 flex-col border-r border-cn-border bg-cn-surface">
                  <ToolPanel tool={tool} time={time} onSeek={setTime} onSelection={(text) => setContexts(text ? [{ id: 'cap-sel', kind: 'caption', label: text.length > 40 ? `${text.slice(0, 38)}…”` : text }] : [CHIP_CLIP])} onOpenLibrary={() => toast.show({ title: 'Opens /dashboard/library', description: 'Owned by the library screens.' })} />
                </aside>
              )}
              <div className="flex min-w-0 flex-1 flex-col">
                {player(false)}
                {timeline(false)}
              </div>
              <div className="flex w-96 shrink-0 flex-col border-l border-cn-border">{conversation(false)}</div>
            </div>
          </div>
        )}

        {device === 'tablet' && (
          <>
            {topBar(false)}
            <div className="flex min-h-0 flex-1">
              <div className="relative flex min-w-0 flex-1 flex-col">
                {player(false)}
                {timeline(true)}
                <ToolRail tool={tool} onTool={setTool} orientation="horizontal" />
                {tool && (
                  <div className="absolute inset-x-0 bottom-14 z-cn-raised flex h-1/2 flex-col rounded-t-cn-xl border border-cn-border-strong bg-cn-surface-raised shadow-cn-3">
                    <div className="flex justify-end p-1">
                      <IconButton size="sm" label="Close tool" icon={<X />} onClick={() => setTool(null)} />
                    </div>
                    <ToolPanel tool={tool} time={time} onSeek={setTime} onSelection={() => undefined} onOpenLibrary={() => undefined} />
                  </div>
                )}
              </div>
              <div className="flex w-80 shrink-0 flex-col border-l border-cn-border">{conversation(false)}</div>
            </div>
          </>
        )}

        {device === 'phone' && (
          <>
            {topBar(true)}
            <div className="relative flex min-h-0 flex-1 flex-col">
              {player(true)}
              {timeline(true)}
              {/* The docked prompt: one line of status, opens the sheet. */}
              <button
                type="button"
                onClick={() => setSheet(true)}
                aria-expanded={sheet}
                className={cx('flex h-14 shrink-0 items-center gap-2 border-t border-cn-border bg-cn-surface px-3 text-left', focusRing)}
              >
                <MessageSquare aria-hidden className="size-4 shrink-0 text-cn-accent-text" />
                <span className="min-w-0 flex-1 truncate text-cn-label">
                  {runLine ? (
                    <WorkingText>{runLine.steps.find((step) => step.status === 'active')?.label ?? 'Reading your request'}</WorkingText>
                  ) : lastTurn?.result?.version ? (
                    <span className="text-cn-fg-secondary">Done · {lastTurn.result.version.name}</span>
                  ) : (
                    <span className="text-cn-fg-muted">Describe an edit to {CLIP.title}</span>
                  )}
                </span>
                <ChevronUp aria-hidden className="size-4 text-cn-fg-muted" />
              </button>
              {sheet && (
                <div role="dialog" aria-modal="true" aria-label="Prompt" className="absolute inset-x-0 bottom-0 z-cn-drawer flex h-[62%] flex-col rounded-t-cn-xl border border-cn-border-strong bg-cn-surface shadow-cn-3">
                  <div className="flex items-center gap-2 px-3 pt-2">
                    <span aria-hidden className="mx-auto h-1 w-10 rounded-cn-full bg-cn-border-strong" />
                    <IconButton size="sm" label="Close" icon={<X />} onClick={() => setSheet(false)} className="absolute right-2 top-1.5" />
                  </div>
                  {conversation(true)}
                </div>
              )}
            </div>
          </>
        )}
      </DeviceFrame>

      <Drawer open={history} onOpenChange={setHistory} title="Version history" description={`${CLIP.title} · ${versions.length} versions`} side={device === 'phone' ? 'bottom' : 'right'}>
        <VersionHistoryList
          versions={versions}
          viewingId={viewingId}
          restoringId={restoringId}
          onView={(id) => {
            setViewingId(id);
            setHistory(false);
          }}
          onRestore={restore}
          onToggleBookmark={(id) => setVersions(versions.map((version) => (version.id === id ? { ...version, bookmarked: !version.bookmarked } : version)))}
          onRename={(id, name) => setVersions(versions.map((version) => (version.id === id ? { ...version, name } : version)))}
        />
      </Drawer>
      <ShortcutsDialog open={shortcuts} onOpenChange={setShortcuts} />
    </ScreenShell>
  );
}
