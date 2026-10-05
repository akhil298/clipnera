'use client';

import { ArrowDown, FileWarning, Pencil, Upload, WifiOff } from 'lucide-react';
import { type KeyboardEvent, type RefObject, useEffect, useMemo, useRef, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { ChoiceCard } from '@/components/ui/ChoiceCard';
import { ContextChip, type PromptContext } from '@/components/ui/ContextChip';
import { IconButton } from '@/components/ui/IconButton';
import { PromptBar, type PromptMode } from '@/components/ui/PromptBar';
import { ResultMessage } from '@/components/ui/ResultMessage';
import { StepList } from '@/components/ui/StepList';
import { useToast } from '@/components/ui/Toast';
import { WorkingText } from '@/components/ui/WorkingText';
import { cx, focusRing } from '@/lib/design/styles';

import { BrollPick } from './BrollPick';
import { CheckInCard } from './CheckInCard';
import { MediaCard, Poster } from './MediaCard';
import { PromptQueue } from './PromptQueue';
import type { Suggestion } from './run/events';
import { SCENARIOS } from './run/scenarios';
import type { RunSimulator, TurnView } from './run/useRunSimulator';
import { BROLL_ALTERNATES, CHIP_CLIP, clock } from './sample';
import { filterCommands, type SlashCommand, SlashMenu } from './SlashMenu';
import { StreamedText } from './StreamedText';

const TERMINAL = ['succeeded', 'partial', 'failed', 'cancelled'];

/** Timeline operations in plain words, per version (the server's shared `describe_op`). */
const OPERATIONS: Record<string, string[]> = {
  'Trimmed silences, added captions': [
    'Trimmed Opening, The price and The close: 14 cuts, 42 seconds',
    'Moved The price to 0:09 and The close to 0:19',
    'Turned captions on: Bold pop, English, following the speech',
  ],
  'Trimmed silences': ['Trimmed Opening, The price and The close: 14 cuts, 42 seconds'],
  'Added B-roll at 0:12': ['Added a B-roll track', 'Placed “Pouring coffee” at 0:12 – 0:16, muted, 4-frame fade in'],
  'Cut to the best 15 seconds': ['Removed 20 lines (57 seconds)', 'Kept lines 2, 9 and 14'],
  'Punchier hook': ['Changed the title text to “₹499 beat ₹999. Here’s why.”'],
  'Bigger captions': ['Caption size 64 → 77 on 9 lines'],
};

function elapsed(turn: TurnView, now: number): string {
  return clock(((turn.endedAt ?? now) - turn.startedAt) / 1000);
}

function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

/* ───────────────────────── messages ───────────────────────── */

function UserMessage({ turn, onEditResend }: { turn: TurnView; onEditResend: (turn: TurnView) => void }) {
  return (
    <div className="group flex flex-col items-end gap-1.5">
      {turn.chips.length > 0 && (
        <div className="flex flex-wrap justify-end gap-1">
          {turn.chips.map((chip) => (
            <ContextChip key={chip.id} context={chip} className="h-6" />
          ))}
        </div>
      )}
      <div className="flex max-w-[88%] items-start gap-1">
        <IconButton
          size="sm"
          label="Edit and resend"
          icon={<Pencil />}
          onClick={() => onEditResend(turn)}
          className="opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
        />
        <p className="rounded-cn-lg bg-cn-surface-hover px-3 py-2 text-cn-body text-cn-fg">
          {turn.mode !== 'edit' && <span className="mr-1.5 text-cn-caption font-semibold text-cn-fg-muted">{turn.mode === 'ask' ? 'Ask' : 'Plan'}</span>}
          {turn.prompt}
        </p>
      </div>
    </div>
  );
}

/** Ask-mode answers turn timecodes into Moment chips that seek the preview. */
function AnswerText({ text, onSeek }: { text: string; onSeek?: (time: string) => void }) {
  const parts = text.split(/(\d:\d\d)/g);
  return (
    <p className="text-cn-body text-cn-fg">
      {parts.map((part, index) =>
        /^\d:\d\d$/.test(part) ? (
          <button
            key={index}
            type="button"
            onClick={() => onSeek?.(part)}
            aria-label={`Play from ${part}`}
            className={cx('mx-0.5 inline-flex h-6 items-center rounded-cn-sm border border-cn-border-strong bg-cn-surface px-1.5 align-baseline font-cn-mono text-cn-caption tabular-nums text-cn-accent-text hover:bg-cn-surface-hover', focusRing)}
          >
            {part}
          </button>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </p>
  );
}

/** Plan mode: a plan the person edits, then approves. Nothing changes until then. */
function PlanDocument({ steps, cost, onApprove }: { steps: { id: string; label: string }[]; cost: number; onApprove: (steps: string[]) => void }) {
  const [editing, setEditing] = useState(false);
  const [items, setItems] = useState(steps.map((step) => step.label));
  const [approved, setApproved] = useState(false);
  return (
    <section aria-label="Plan" className="flex flex-col gap-3 rounded-cn-lg border border-cn-border-strong bg-cn-surface p-3.5">
      <ol className="flex flex-col gap-1.5">
        {items.map((item, index) => (
          <li key={index} className="flex items-start gap-2 text-cn-label">
            <span className="mt-0.5 w-4 shrink-0 font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">{index + 1}</span>
            {editing ? (
              <input
                aria-label={`Plan step ${index + 1}`}
                value={item}
                onChange={(event) => setItems(items.map((other, i) => (i === index ? event.target.value : other)))}
                className={cx('h-7 w-full rounded-cn-sm border border-cn-control-border bg-cn-field px-2 text-cn-label text-cn-fg', focusRing)}
              />
            ) : (
              <span className="text-cn-fg">{item}</span>
            )}
          </li>
        ))}
      </ol>
      <p className="text-cn-caption text-cn-fg-muted">Uses about {cost} credits when you approve. Nothing has changed yet.</p>
      {approved ? (
        <p className="text-cn-caption text-cn-fg-muted">Approved. Running it as an edit below.</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            onClick={() => {
              setApproved(true);
              onApprove(items);
            }}
          >
            Approve and run · {cost} credits
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setEditing(!editing)}>
            {editing ? 'Done editing' : 'Edit plan'}
          </Button>
        </div>
      )}
    </section>
  );
}

interface TurnActions {
  onAnswer: (choice: string) => void;
  onDecide: (decision: 'continue' | 'finish' | 'add_credits') => void;
  onUndo: (turn: TurnView, undone: boolean) => void;
  onCompare?: () => void;
  onSuggestion: (prompt: string) => void;
  onRetry: (turn: TurnView) => void;
  onApprovePlan: (steps: string[]) => void;
  onSeek?: (time: string) => void;
  onOpenLibrary?: (query: string) => void;
}

const lookup = (suggestions: ReadonlyArray<Suggestion>, label: string) => suggestions.find((item) => item.label === label)?.prompt ?? label;

function AssistantTurn({ turn, now, actions }: { turn: TurnView; now: number; actions: TurnActions }) {
  const [stepsOpen, setStepsOpen] = useState(false);
  const ended = TERMINAL.includes(turn.status);
  const reading = turn.status === 'sending' || (turn.status === 'acknowledged' && !turn.planText);
  const timestamp = ended ? `${elapsed(turn, now)} · just now` : undefined;

  if (turn.status === 'queued') return <p className="text-cn-label text-cn-fg-muted">Waiting for the edit before this one.</p>;

  return (
    <div className="flex flex-col gap-3">
      {reading && (
        <p className="flex flex-wrap items-center gap-1.5 text-cn-label">
          <WorkingText>Reading your request</WorkingText>
          {turn.chips.map((chip) => (
            <ContextChip key={chip.id} context={chip} className="h-6" />
          ))}
        </p>
      )}

      {turn.mode === 'ask' && turn.answerText && !turn.result && <StreamedText text={turn.answerText} className="text-cn-body text-cn-fg" />}
      {turn.mode !== 'ask' && turn.planText && <StreamedText text={turn.planText} done={Boolean(turn.planSteps)} className="text-cn-body text-cn-fg" />}
      {turn.mode === 'edit' && turn.credits && turn.credits.estimate > 0 && turn.planText && !ended && (
        <p className="text-cn-caption text-cn-fg-muted">Uses about {turn.credits.estimate} credits</p>
      )}

      {turn.question && (
        <ChoiceCard
          question={turn.question.text}
          choices={turn.question.choices.map((choice, index) => ({
            id: choice.id,
            label: choice.label,
            description: choice.hint,
            preview: turn.question?.text.startsWith('I’m not sure') ? <Poster tone={index} className="w-8 rounded-cn-xs" /> : undefined,
          }))}
          onChoose={actions.onAnswer}
          onSkip={() => actions.onAnswer('skip')}
          chosenId={turn.question.chosenId}
        />
      )}

      {turn.pause && <CheckInCard pause={turn.pause} onDecide={actions.onDecide} />}

      {turn.mode === 'edit' && turn.steps.length > 0 && !ended && (
        <>
          <StepList steps={turn.steps} elapsed={elapsed(turn, now)} expanded={stepsOpen} onExpandedChange={setStepsOpen} />
          {turn.stopping && <p className="text-cn-caption text-cn-fg-muted">Stopping after this step. Anything already done is kept.</p>}
        </>
      )}

      {turn.mode === 'plan' && turn.result?.plan_document && (
        <PlanDocument steps={turn.result.plan_document.steps} cost={turn.credits?.estimate ?? 6} onApprove={actions.onApprovePlan} />
      )}

      {turn.mode === 'ask' && turn.result && (
        <div className="flex flex-col gap-2">
          <AnswerText text={turn.result.answer ?? turn.answerText} onSeek={actions.onSeek} />
          <p className="text-cn-caption text-cn-fg-muted">Free · 17 of 20 questions left today. Nothing was changed.</p>
          <div className="flex flex-wrap gap-2">
            {turn.result.suggestions.map((suggestion) => (
              <Button key={suggestion.label} size="sm" variant="secondary" onClick={() => actions.onSuggestion(suggestion.prompt)}>
                Make it an edit: {suggestion.label}
              </Button>
            ))}
          </div>
        </div>
      )}

      {turn.mode === 'edit' && turn.result && (
        <>
          <ResultMessage
            status={turn.result.status === 'succeeded' ? 'done' : turn.stopping ? 'stopped' : 'partial'}
            summary={
              turn.result.version === null && turn.result.summary.not_done.length > 0
                ? `There isn’t enough footage to do this. ${turn.steps.find((step) => step.status === 'done')?.detail ?? ''}.`
                : turn.stopping
                  ? `Stopped — ${turn.result.summary.done.length} of ${turn.result.summary.done.length + turn.result.summary.not_done.length} done.`
                  : turn.result.status === 'succeeded'
                    ? `Done — ${turn.result.summary.done.join('; ').replace(/^./, (letter) => letter.toLowerCase())}.`
                    : 'Partly done.'
            }
            changes={turn.result.status === 'succeeded' ? [] : turn.result.summary.done}
            notDone={turn.result.summary.not_done.map((item) => ({ label: item.text, reason: item.reason }))}
            safeNote={turn.result.version === null ? 'Nothing was changed.' : undefined}
            version={
              turn.result.version
                ? {
                    name: turn.result.version.name,
                    undone: turn.undone,
                    onUndo: () => actions.onUndo(turn, true),
                    onRedo: () => actions.onUndo(turn, false),
                    onCompare: actions.onCompare,
                  }
                : undefined
            }
            details={{
              steps: turn.steps,
              operations: OPERATIONS[turn.result.version?.name ?? ''] ?? (turn.result.summary.done.length ? turn.result.summary.done : ['No timeline changes']),
            }}
            suggestions={turn.result.suggestions.map((suggestion) => suggestion.label)}
            onSuggestion={(label) => actions.onSuggestion(lookup(turn.result?.suggestions ?? [], label))}
            timestamp={timestamp}
          />
          {turn.pick && !turn.undone && <BrollPick pick={turn.pick} onOpenLibrary={actions.onOpenLibrary} />}
        </>
      )}

      {turn.failure && <FailureMessage turn={turn} actions={actions} timestamp={timestamp} />}

      {turn.cancelled && (
        <p className="text-cn-label text-cn-fg-secondary">
          {turn.pause?.reason === 'approval' ? 'Not started. Nothing was changed.' : 'Stopped. Nothing was changed.'}
        </p>
      )}
    </div>
  );
}

function FailureMessage({ turn, actions, timestamp }: { turn: TurnView; actions: TurnActions; timestamp?: string }) {
  const failure = turn.failure;
  if (!failure) return null;
  const { error, version, suggestion } = failure;

  if (error.code === 'SECOND_FAILURE') {
    return (
      <div className="flex flex-col gap-2">
        <ResultMessage
          status="failed"
          summary="That didn’t work twice."
          safeNote="Your earlier versions are untouched. Try a different prompt:"
          suggestions={suggestion ? [suggestion.label] : []}
          onSuggestion={() => suggestion && actions.onSuggestion(suggestion.prompt)}
          details={{ steps: turn.steps, operations: ['No timeline changes'] }}
          timestamp={timestamp}
        />
        <a href="mailto:support@clipnera.com" className={cx('ml-7 self-start rounded-cn-xs text-cn-label font-semibold text-cn-accent-text hover:underline', focusRing)}>
          Contact support
        </a>
      </div>
    );
  }

  if (error.code === 'MEDIA_UNREADABLE') {
    return (
      <div className="flex flex-col gap-2">
        <ResultMessage status="failed" summary={error.message} safeNote="Nothing was changed. Convert it to MP4 with AAC audio, then replace it." timestamp={timestamp} />
        <div className="ml-7">
          <Button size="sm" leadingIcon={<Upload />}>
            Replace file
          </Button>
        </div>
      </div>
    );
  }

  return (
    <ResultMessage
      status="failed"
      summary={error.message}
      safeNote={version ? `“${version.name}” is kept as a version.` : 'Nothing was changed.'}
      onRetry={error.retryable ? () => actions.onRetry(turn) : undefined}
      version={version ? { name: version.name, undone: turn.undone, onUndo: () => actions.onUndo(turn, true), onRedo: () => actions.onUndo(turn, false) } : undefined}
      details={{ steps: turn.steps, operations: OPERATIONS[version?.name ?? ''] ?? ['No timeline changes'] }}
      timestamp={timestamp}
    />
  );
}

/* ───────────────────────── panel ───────────────────────── */

export interface ConversationPanelProps {
  sim: RunSimulator;
  onCompare?: () => void;
  onSeek?: (time: string) => void;
  onOpenLibrary?: (query: string) => void;
  /** Selection from the timeline, transcript or library, as chips. */
  contexts: PromptContext[];
  onContextsChange: (contexts: PromptContext[]) => void;
  promptRef?: RefObject<HTMLTextAreaElement | null>;
  /** Phone sheet: no header, tighter padding. */
  compact?: boolean;
  className?: string;
}

/**
 * The conversation panel: messages, queue, and the docked prompt bar. Every
 * visible state comes from the run view model built from events.
 */
export function ConversationPanel({ sim, onCompare, onSeek, onOpenLibrary, contexts, onContextsChange, promptRef, compact = false, className }: ConversationPanelProps) {
  const toast = useToast();
  const [value, setValue] = useState('');
  const [mode, setMode] = useState<PromptMode>('edit');
  const [slashActive, setSlashActive] = useState(0);
  const [slashDismissed, setSlashDismissed] = useState(false);
  const [resending, setResending] = useState<TurnView | null>(null);
  const [atBottom, setAtBottom] = useState(true);
  const [announcement, setAnnouncement] = useState('');
  const localRef = useRef<HTMLTextAreaElement>(null);
  const textareaRef = promptRef ?? localRef;
  const logRef = useRef<HTMLDivElement>(null);
  const now = useNow(sim.running);

  const slashOpen = value.startsWith('/') && !slashDismissed && value.length < 24;
  const slashItems = useMemo(() => (slashOpen ? filterCommands(value) : []), [slashOpen, value]);
  const brollQuery = value.startsWith('Add B-roll of ') ? value.slice(14).split(' at ')[0].split(' over ')[0].trim() : '';

  // Keep the newest message in view unless the person has scrolled up.
  const lastTurn = sim.turns[sim.turns.length - 1];
  useEffect(() => {
    const log = logRef.current;
    if (log && atBottom) log.scrollTop = log.scrollHeight;
  });

  // One polite announcement per result; steps announce themselves (StepList).
  useEffect(() => {
    if (!lastTurn) return;
    if (lastTurn.result) setAnnouncement(`${lastTurn.result.status === 'succeeded' ? 'Done' : 'Partly done'}: ${lastTurn.result.version?.name ?? 'answer ready'}`);
    else if (lastTurn.failure) setAnnouncement(`Not done: ${lastTurn.failure.error.message}`);
    else if (lastTurn.status === 'sending') setAnnouncement('Sent. Reading your request.');
  }, [lastTurn]);

  const fill = (text: string) => {
    setValue(text);
    requestAnimationFrame(() => {
      const textarea = textareaRef.current;
      if (!textarea) return;
      textarea.focus();
      const caret = text.indexOf('  ') >= 0 ? text.indexOf('  ') + 1 : text.length;
      textarea.setSelectionRange(caret, caret);
    });
  };

  const pickCommand = (item: SlashCommand) => {
    setSlashDismissed(true);
    if (item.group === 'Go to') {
      setValue('');
      toast.show({ title: `${item.description}`, description: 'Navigation is not wired in this mockup.' });
      return;
    }
    fill(item.template(contexts));
  };

  const onKeyDownCapture = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!slashOpen || !(event.target instanceof HTMLTextAreaElement)) return;
    const count = slashItems.length;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      event.stopPropagation();
      if (count) setSlashActive((index) => (index + (event.key === 'ArrowDown' ? 1 : -1) + count) % count);
    } else if ((event.key === 'Enter' || event.key === 'Tab') && count) {
      event.preventDefault();
      event.stopPropagation();
      pickCommand(slashItems[Math.min(slashActive, count - 1)]);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      setSlashDismissed(true);
    }
  };

  const submit = () => {
    const text = value.trim();
    if (!text) return;
    setValue('');
    if (sim.running) {
      sim.enqueue(text, contexts);
      return;
    }
    const known = SCENARIOS.find((scenario) => scenario.prompt === text.toLowerCase());
    const scenarioId = known?.id ?? (mode === 'ask' ? 'ask' : mode === 'plan' ? 'plan' : 'happy');
    sim.start(scenarioId, { keep: true, prompt: text });
    setResending(null);
    setAtBottom(true);
  };

  const actions: TurnActions = {
    onAnswer: sim.answer,
    onDecide: sim.decide,
    onUndo: (turn, undone) => sim.undo(turn.id, undone),
    onCompare,
    onSuggestion: (prompt) => {
      setMode('edit');
      fill(prompt);
    },
    onRetry: () => sim.start('second-failure', { keep: true, prompt: 'Try again: add captions' }),
    onApprovePlan: (steps) => sim.start('happy', { keep: true, prompt: `Approved plan: ${steps[0].toLowerCase()} …` }),
    onSeek,
    onOpenLibrary,
  };

  return (
    <section aria-label="Conversation" className={cx('flex min-h-0 flex-col bg-cn-surface', className)}>
      {!compact && (
        <div className="flex h-11 shrink-0 items-center gap-2 border-b border-cn-border px-4">
          <h2 className="text-cn-label font-semibold">Conversation</h2>
          <span className="text-cn-caption text-cn-fg-muted">· {sim.editor.versionCount} versions</span>
        </div>
      )}
      <span className="sr-only" role="status" aria-live="polite">
        {announcement}
      </span>

      {!sim.editor.online && (
        <p role="status" className="flex items-center gap-2 border-b border-cn-border bg-cn-surface-hover px-4 py-2 text-cn-label">
          <WifiOff aria-hidden className="size-4 text-cn-fg-muted" />
          <WorkingText>Reconnecting — your edit is still running.</WorkingText>
        </p>
      )}
      {sim.editor.catchingUp && (
        <p role="status" className="border-b border-cn-border px-4 py-2 text-cn-label">
          <WorkingText>Catching up</WorkingText>
        </p>
      )}

      <div
        ref={logRef}
        role="log"
        aria-label="Messages"
        aria-live="off"
        onScroll={(event) => {
          const el = event.currentTarget;
          setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 48);
        }}
        className={cx('relative min-h-0 flex-1 overflow-y-auto', compact ? 'px-3 py-3' : 'px-4 py-4')}
      >
        {sim.turns.length === 0 ? (
          <div className="flex h-full flex-col justify-end gap-3 pb-2">
            <p className="text-cn-body font-semibold text-cn-fg">What should change in “{CHIP_CLIP.label}”?</p>
            <p className="text-cn-label text-cn-fg-secondary">Select a clip, words or a range to point at it. Type / for commands.</p>
            <ul aria-label="Suggestions" className="flex flex-wrap gap-1.5">
              {['remove the silences and add captions', 'add B-roll where I talk about coffee', 'where do I talk about coffee?'].map((suggestion) => (
                <li key={suggestion}>
                  <Button size="sm" variant="secondary" onClick={() => fill(suggestion)}>
                    {suggestion}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <ol className="flex flex-col gap-5">
            {sim.turns.map((turn) => (
              <li key={turn.id} className="flex flex-col gap-3">
                <UserMessage
                  turn={turn}
                  onEditResend={(sent) => {
                    setResending(sent);
                    setMode(sent.mode);
                    onContextsChange(sent.chips);
                    fill(sent.prompt);
                  }}
                />
                <AssistantTurn turn={turn} now={now} actions={actions} />
              </li>
            ))}
          </ol>
        )}
      </div>

      {!atBottom && (
        <div className="relative">
          <Button
            size="sm"
            variant="secondary"
            leadingIcon={<ArrowDown />}
            onClick={() => {
              setAtBottom(true);
              logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
            }}
            className="absolute -top-11 left-1/2 -translate-x-1/2 shadow-cn-2"
          >
            Jump to latest
          </Button>
        </div>
      )}

      <div className={cx('flex shrink-0 flex-col gap-2 border-t border-cn-border', compact ? 'p-2' : 'p-3')} onKeyDownCapture={onKeyDownCapture}>
        <PromptQueue items={sim.queue} onChange={sim.setQueue} />
        {resending && (
          <p className="flex items-center gap-2 rounded-cn-md bg-cn-surface-hover px-3 py-1.5 text-cn-caption text-cn-fg-secondary">
            <FileWarning aria-hidden className="size-3.5 shrink-0" />
            <span className="flex-1">Editing a sent prompt. Sending returns the project to before it, then runs the new one.</span>
            <button type="button" onClick={() => setResending(null)} className={cx('rounded-cn-xs font-semibold hover:text-cn-fg', focusRing)}>
              Cancel
            </button>
          </p>
        )}
        {slashOpen && (
          <SlashMenu
            query={value}
            items={slashItems}
            activeIndex={Math.min(slashActive, Math.max(slashItems.length - 1, 0))}
            onPick={pickCommand}
            onHover={setSlashActive}
            textarea={textareaRef.current}
          />
        )}
        {brollQuery.length > 2 && (
          <div aria-label={`Top matches for ${brollQuery}`} role="group" className="rounded-cn-lg border border-cn-border bg-cn-surface p-2">
            <p className="mb-1.5 text-cn-caption text-cn-fg-muted">Top matches · click one to use it</p>
            <ul className="grid grid-cols-4 gap-1.5">
              {BROLL_ALTERNATES.map((shot) => (
                <li key={shot.id}>
                  <MediaCard
                    size="sm"
                    title={shot.title}
                    length={shot.length}
                    tone={shot.tone}
                    actionLabel={`Use ${shot.title}`}
                    onOpen={() => {
                      onContextsChange([...contexts.filter((context) => context.kind !== 'asset'), { id: `asset-${shot.id}`, kind: 'asset', label: shot.title, meta: shot.length }]);
                      fill('Use this clip at ');
                    }}
                  />
                </li>
              ))}
            </ul>
          </div>
        )}
        <PromptBar
          ref={textareaRef}
          value={value}
          onValueChange={(next) => {
            setValue(next);
            if (!next.startsWith('/')) setSlashDismissed(false);
            setSlashActive(0);
          }}
          onSubmit={submit}
          mode={mode}
          onModeChange={setMode}
          running={sim.running}
          onStop={sim.stop}
          contexts={contexts}
          onRemoveContext={(id) => onContextsChange(contexts.filter((context) => context.id !== id))}
          onAttach={() => toast.show({ title: 'Attach a video, image, audio or link', description: 'Opens the file picker in the real screen.' })}
          creditCost={mode === 'edit' && value.trim() && !value.startsWith('/') ? 4 : undefined}
          queueCount={sim.queue.length}
          label="Prompt"
        />
      </div>
    </section>
  );
}
