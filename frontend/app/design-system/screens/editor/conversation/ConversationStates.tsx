'use client';

import { Lock, RotateCcw } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { ContextChip, type PromptContext } from '@/components/ui/ContextChip';
import { PromptBar } from '@/components/ui/PromptBar';
import { ResultMessage } from '@/components/ui/ResultMessage';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { useToast } from '@/components/ui/Toast';
import { CheckInCard, PromptQueue, SLASH_COMMANDS } from '@/components/ui';
import { cx } from '@/lib/design/styles';

import { ConversationPanel } from '../_components/Conversation';
import type { RunStatus } from '../_components/run/events';
import { SCENARIOS } from '../_components/run/scenarios';
import { type QueuedPrompt, type Speed, useRunSimulator } from '../_components/run/useRunSimulator';
import { CHIP_CAPTION, CHIP_CLIP, CHIP_RANGE } from '../_components/sample';
import { ScreenShell, StateSwitcher } from '../_components/ScreenShell';
import { ITEM_LOCKED_COPY } from '../_components/Timeline';

/** Run status → what the conversation shows (backend §4.2; one row per status). */
const STATUS_MAP: ReadonlyArray<[RunStatus | 'sending', string]> = [
  ['sending', 'Your message, then “Reading your request” with the chips (client-only, < 100 ms)'],
  ['queued', 'Numbered item in “Up next”; position from queue_position'],
  ['acknowledged', '“Reading your request”; credit estimate becomes known'],
  ['planning', 'Plan text streaming in word groups; then the step outline'],
  ['awaiting_input', 'Choice card; the run waits; number keys pick'],
  ['executing', 'One-line step list: label · step n of N · progress · elapsed'],
  ['paused', 'Check-in card: approval, or credits (pause, not fail)'],
  ['stopping', '“Stopping after this step. Anything already done is kept.”'],
  ['checking', 'Step “Checking the result”'],
  ['succeeded', 'Steps fold away; result with version, Undo, Compare, next steps'],
  ['partial', 'Result with a “Not done” box and “Try the rest”'],
  ['failed', 'What happened, what is safe, one action; failed step stays visible'],
  ['cancelled', '“Stopped. Nothing was changed.”'],
];

const EPHEMERAL = new Set(['run.plan.delta', 'run.message.delta', 'run.step.progress', 'sync.reset', 'client.connection']);

const SPEEDS = [
  { value: '0.5', label: '0.5×' },
  { value: '1', label: '1×' },
  { value: '2', label: '2×' },
];

const QUEUE: QueuedPrompt[] = [
  { id: 'a', prompt: 'make the captions bigger', chips: [] },
  { id: 'b', prompt: 'add B-roll over the price line', chips: [CHIP_RANGE] },
  { id: 'c', prompt: 'export for Reels', chips: [] },
];

export function ConversationStates() {
  const toast = useToast();
  const sim = useRunSimulator(40);
  const [scenario, setScenario] = useState('happy');
  const [contexts, setContexts] = useState<PromptContext[]>([CHIP_CLIP]);
  const [queue, setQueue] = useState(QUEUE);
  const [slashText, setSlashText] = useState('/c');
  const [promptState, setPromptState] = useState('offline');
  const status = sim.turns[sim.turns.length - 1]?.status;

  const controls = (
    <>
      <StateSwitcher label="Prompt run" options={SCENARIOS.map((item) => ({ value: item.id, label: item.label }))} value={scenario} onChange={setScenario} />
      <Button size="sm" leadingIcon={<RotateCcw />} onClick={() => sim.start(scenario)}>
        Play this run
      </Button>
      <SegmentedControl label="Replay speed" size="sm" options={SPEEDS} value={String(sim.speed)} onValueChange={(value) => sim.setSpeed(Number(value) as Speed)} />
      <p className="w-full text-cn-caption text-cn-fg-muted">{SCENARIOS.find((item) => item.id === scenario)?.note}</p>
    </>
  );

  return (
    <ScreenShell title="Conversation panel" summary="Every run status and event, live, plus each part in isolation." flags={['new_ui_editor', 'prompt_streaming_v2']} controls={controls}>
      <div className="grid gap-6 xl:grid-cols-[24rem_1fr_18rem]">
        <div className="h-[44rem] overflow-hidden rounded-cn-xl border border-cn-border">
          <ConversationPanel sim={sim} contexts={contexts} onContextsChange={setContexts} className="h-full" />
        </div>

        <Card padding="md">
          <CardHeader title="Run status → what the panel shows" description="The row lit amber is the live status of the newest run." level={2} />
          <table className="mt-3 w-full text-left text-cn-label">
            <caption className="sr-only">Run statuses and their visible state</caption>
            <thead>
              <tr className="text-cn-caption text-cn-fg-muted">
                <th scope="col" className="w-36 py-1.5 font-semibold">Status</th>
                <th scope="col" className="py-1.5 font-semibold">Shows</th>
              </tr>
            </thead>
            <tbody>
              {STATUS_MAP.map(([name, shows]) => (
                <tr key={name} aria-current={status === name || undefined} className={cx('border-t border-cn-border', status === name && 'bg-cn-accent-subtle')}>
                  <td className={cx('py-1.5 pr-2 font-cn-mono text-cn-caption', status === name ? 'text-cn-accent-text' : 'text-cn-fg-secondary')}>{name}</td>
                  <td className="py-1.5 text-cn-fg-secondary">{shows}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        <Card padding="md" className="max-h-[44rem] overflow-y-auto">
          <CardHeader title="Event log" description="Events this run emitted, in order. Ephemeral ones are marked." level={2} />
          {sim.log.length === 0 ? (
            <p className="mt-3 text-cn-label text-cn-fg-muted">Press “Play this run”.</p>
          ) : (
            <ol className="mt-3 flex flex-col gap-1">
              {sim.log.map((entry) => (
                <li key={entry.seq} className="flex items-baseline gap-2 font-cn-mono text-cn-caption">
                  <span className="w-6 shrink-0 tabular-nums text-cn-fg-muted">{entry.seq}</span>
                  <span className={cx('min-w-0 flex-1 truncate', EPHEMERAL.has(entry.type) ? 'text-cn-fg-muted' : 'text-cn-fg')}>{entry.type}</span>
                  {entry.buffered && <span className="text-cn-accent-text">missed</span>}
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      <h2 className="mb-3 mt-10 text-cn-title-sm font-semibold">Parts, in isolation</h2>
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        <Card padding="md">
          <CardHeader title="Slash menu" description="Typing “/c” filters. ↑↓ move, Enter or Tab fill, Escape closes." level={3} />
          <div className="mt-80">
            <PromptBar value={slashText} onValueChange={setSlashText} onSubmit={() => undefined} slashCommands={SLASH_COMMANDS} label="Slash menu demo" />
          </div>
        </Card>
        <Card padding="md">
          <CardHeader title="Prompt queue" description="Edit, reorder by buttons, remove. Collapses past two." level={3} />
          <PromptQueue items={queue} onChange={setQueue} className="mt-3" />
        </Card>
        <Card padding="md">
          <CardHeader title="Locked context chip" description="A chip for an item the run is working on: no remove until the step ends." level={3} />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-cn-sm opacity-60" aria-label={`Clip: The price, locked. ${ITEM_LOCKED_COPY}`}>
              <ContextChip context={{ id: 'l', kind: 'clip', label: 'The price', meta: '0:10' }} />
              <Lock aria-hidden className="size-3.5 text-cn-fg-muted" />
            </span>
            <ContextChip context={CHIP_CAPTION} onRemove={() => undefined} />
          </div>
        </Card>
        <Card padding="md">
          <CardHeader title="Check-in: approval" level={3} />
          <CheckInCard
            className="mt-3"
            onDecide={() => undefined}
            checkIn={{ reason: 'approval', credits: { estimate: 84, spent: 0 }, approval: { text: 'This edit costs more than 60 credits.' }, options: ['continue', 'finish'] }}
          />
        </Card>
        <Card padding="md">
          <CardHeader title="Check-in: out of credits" level={3} />
          <CheckInCard className="mt-3" onDecide={() => undefined} checkIn={{ reason: 'credits', credits: { estimate: 4, spent: 4 }, needed: 3, options: ['add_credits', 'finish'] }} />
        </Card>
        <Card padding="md">
          <CardHeader title="Check-in: spend threshold" level={3} />
          <CheckInCard className="mt-3" onDecide={() => undefined} checkIn={{ reason: 'credits', credits: { estimate: 70, spent: 61 }, options: ['continue', 'finish'] }} />
        </Card>
        <Card padding="md">
          <CardHeader title="Stopped with changes kept" level={3} />
          <ResultMessage
            className="mt-3"
            status="stopped"
            summary="Stopped — 1 of 2 done."
            changes={['Removed 14 silences (42 seconds)']}
            notDone={[{ label: 'Adding captions', reason: 'stopped before this step' }]}
            version={{ name: 'Trimmed silences', onUndo: () => undefined, onCompare: () => undefined }}
            suggestions={['Try the rest']}
            onSuggestion={() => undefined}
          />
        </Card>
        <Card padding="md">
          <CardHeader title="Conflicts and locks (toasts)" description="423 ITEM_LOCKED, 409 STALE_VERSION, 409 UNDO_WOULD_DISCARD, a send that failed." level={3} />
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" onClick={() => toast.show({ title: 'This clip is locked for a moment', description: ITEM_LOCKED_COPY })}>
              423 locked
            </Button>
            <Button size="sm" variant="secondary" onClick={() => toast.show({ title: 'Your edit to Opening was replaced by Clipnera’s change.', action: { label: 'Undo', onClick: () => undefined } })}>
              409 stale
            </Button>
            <Button size="sm" variant="secondary" onClick={() => toast.show({ title: 'Undo would also remove 2 of your hand edits', description: 'They came after this edit. Use version history to pick what to keep.', tone: 'info', action: { label: 'Undo anyway', onClick: () => undefined } })}>
              Undo conflict
            </Button>
            <Button size="sm" variant="secondary" onClick={() => toast.show({ title: 'Not sent. Check your connection.', description: 'Your prompt is still in the bar.', tone: 'danger', action: { label: 'Retry', onClick: () => undefined } })}>
              Send failed
            </Button>
          </div>
        </Card>
        <Card padding="md">
          <CardHeader title="Prompt bar states" level={3} />
          <SegmentedControl
            className="mt-3"
            label="Prompt bar state"
            size="sm"
            value={promptState}
            onValueChange={setPromptState}
            options={[
              { value: 'offline', label: 'Offline' },
              { value: 'loading', label: 'No project yet' },
              { value: 'send-failed', label: 'Send failed' },
            ]}
          />
          <div className="mt-3 flex flex-col gap-1.5">
            <PromptBar
              value={promptState === 'send-failed' ? 'remove the silences and add captions' : ''}
              onValueChange={() => undefined}
              onSubmit={() => undefined}
              mode="edit"
              onModeChange={() => undefined}
              contexts={[CHIP_CLIP]}
              disabled={promptState !== 'send-failed'}
              placeholder={promptState === 'offline' ? 'You’re offline. Prompts send when you’re back.' : promptState === 'loading' ? 'Loading your project' : undefined}
            />
            {promptState === 'send-failed' && (
              <p role="alert" className="flex items-center gap-2 text-cn-label text-cn-danger-text">
                Not sent. Check your connection.
                <Button size="sm" variant="secondary">
                  Retry
                </Button>
              </p>
            )}
            {promptState === 'offline' && <p className="text-cn-caption text-cn-fg-muted">Edits already running carry on without you.</p>}
          </div>
        </Card>
      </div>
    </ScreenShell>
  );
}
