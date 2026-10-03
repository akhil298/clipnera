'use client';

import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { ChoiceCard } from '@/components/ui/ChoiceCard';
import { ContextChip, type PromptContext } from '@/components/ui/ContextChip';
import { PromptBar, type PromptMode } from '@/components/ui/PromptBar';
import { ResultMessage } from '@/components/ui/ResultMessage';
import { type RunStep, StepList } from '@/components/ui/StepList';
import { useToast } from '@/components/ui/Toast';

import { GallerySection, Specimen, State } from './Specimen';

const CONTEXTS: ReadonlyArray<PromptContext> = [
  { id: 'clip', kind: 'clip', label: 'Opening hook', meta: '0:42' },
  { id: 'range', kind: 'range', label: '0:12 – 0:31' },
  { id: 'caption', kind: 'caption', label: '“The first thing we changed was…”' },
  { id: 'asset', kind: 'asset', label: 'City skyline at dusk' },
  { id: 'moment', kind: 'moment', label: '1:07.4' },
];

const RUN_LABELS = ['Reading your request', 'Finding cut points', 'Trimming 14 silences', 'Adding captions', 'Checking the result'];
const RUN_DETAILS = ['', '6 cut points', 'Removed 42 seconds', 'Bold Pop style, 3 clips', 'Frames and audio checked'];

const runSteps = (activeIndex: number): RunStep[] =>
  RUN_LABELS.map((label, index) => ({
    id: label,
    label,
    status: index < activeIndex ? 'done' : index === activeIndex ? 'active' : 'queued',
    detail: index < activeIndex ? RUN_DETAILS[index] || undefined : undefined,
    progress: index === activeIndex && index === 2 ? '9 of 14' : undefined,
  }));

const FAILED_RUN: ReadonlyArray<RunStep> = [
  { id: 'a', label: 'Finding cut points', status: 'done', detail: '6 cut points' },
  { id: 'b', label: 'Adding B-roll', status: 'failed', detail: 'No library shots matched “city at night”.' },
  { id: 'c', label: 'Adding captions', status: 'skipped' },
];

const SUGGESTIONS = ['Make the hook shorter', 'Try a calmer caption style', 'Export all three'];

export function PromptSection() {
  const toast = useToast();
  const [prompt, setPrompt] = useState('');
  const [mode, setMode] = useState<PromptMode>('edit');
  const [contexts, setContexts] = useState<ReadonlyArray<PromptContext>>(CONTEXTS.slice(0, 2));
  const [docked, setDocked] = useState('Also add music under the intro');
  const [dockedMode, setDockedMode] = useState<PromptMode>('edit');
  const [active, setActive] = useState(-1);
  const timer = useRef<ReturnType<typeof setInterval>>(undefined);
  const [choice, setChoice] = useState<string | undefined>(undefined);
  const [undone, setUndone] = useState(false);

  useEffect(() => () => clearInterval(timer.current), []);

  const startRun = () => {
    clearInterval(timer.current);
    setActive(0);
    timer.current = setInterval(() => {
      setActive((index) => {
        if (index >= RUN_LABELS.length) {
          clearInterval(timer.current);
          return index;
        }
        return index + 1;
      });
    }, 1600);
  };

  const running = active >= 0 && active < RUN_LABELS.length;
  const elapsed = `0:${String(Math.max(active, 0) * 2).padStart(2, '0')}`;

  return (
    <GallerySection
      id="prompt"
      title="Prompt experience"
      intro="Presentational components for 01-experience-principles §4–§8. The parent owns all state; nothing here calls the API."
    >
      <Specimen title="PromptBar" note="Enter sends, Shift+Enter adds a line. While running, Send queues and Stop sits beside it; Stop never clears the text.">
        <div className="space-y-6">
          <State label="hero, idle, two context chips, known cost" className="items-stretch">
            <PromptBar
              size="hero"
              value={prompt}
              onValueChange={setPrompt}
              onSubmit={() => {
                toast.show({ title: 'Prompt sent', description: prompt });
                setPrompt('');
              }}
              mode={mode}
              onModeChange={setMode}
              contexts={contexts}
              onRemoveContext={(id) => setContexts((list) => list.filter((context) => context.id !== id))}
              onAttach={() => toast.show({ title: 'Attach picker opens here' })}
              creditCost={mode === 'edit' ? 12 : undefined}
            />
          </State>
          <div className="grid gap-6 md:grid-cols-2">
            <State label="docked, running, 2 queued" className="items-stretch">
              <PromptBar
                value={docked}
                onValueChange={setDocked}
                onSubmit={() => setDocked('')}
                mode={dockedMode}
                onModeChange={setDockedMode}
                running
                queueCount={2}
                onStop={() => toast.show({ title: 'Stopping at the next safe point' })}
              />
            </State>
            <State label="disabled (no project loaded)" className="items-stretch">
              <PromptBar value="" onValueChange={() => {}} onSubmit={() => {}} mode="ask" onModeChange={() => {}} disabled />
            </State>
          </div>
        </div>
      </Specimen>

      <Specimen title="ContextChip" note="Read as “Clip: Opening hook”. Removable in the bar; read-only inside a sent message.">
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {CONTEXTS.map((context) => (
              <ContextChip key={context.id} context={context} onRemove={() => toast.show({ title: `Removed ${context.label}` })} />
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {CONTEXTS.slice(0, 2).map((context) => (
              <ContextChip key={context.id} context={context} />
            ))}
          </div>
        </div>
      </Specimen>

      <Specimen title="StepList" note="One calm line while working; expand for each step. Screen readers hear each new step once.">
        <div className="space-y-6">
          <div className="space-y-3">
            <Button size="sm" variant="secondary" onClick={startRun}>
              {active < 0 ? 'Start a sample run' : 'Run again'}
            </Button>
            <StepList steps={runSteps(active < 0 ? -1 : active)} elapsed={active >= 0 ? elapsed : undefined} defaultExpanded />
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            <State label="failed step, collapsed" className="items-stretch">
              <StepList steps={FAILED_RUN} onRetryStep={() => toast.show({ title: 'Trying the step again' })} />
            </State>
            <State label="all done, collapsed" className="items-stretch">
              <StepList steps={runSteps(RUN_LABELS.length)} elapsed="0:42" />
            </State>
          </div>
        </div>
      </Specimen>

      <Specimen title="ChoiceCard" note="Up to four options and a skip. Number keys pick while the card has focus. Locks once answered.">
        <div className="grid gap-6 md:grid-cols-2">
          <State label={choice ? 'answered' : 'open'} className="items-stretch">
            <ChoiceCard
              question="Which clip should get the new hook?"
              choices={[
                { id: 'a', label: 'Opening hook', description: '0:42 · score 91' },
                { id: 'b', label: 'Pricing story', description: '0:58 · score 84' },
                { id: 'c', label: 'The hiring mistake', description: '0:37 · score 80' },
                { id: 'all', label: 'All three' },
              ]}
              onChoose={setChoice}
              onSkip={() => setChoice('skip')}
              chosenId={choice}
            />
            {choice && (
              <Button size="sm" variant="ghost" onClick={() => setChoice(undefined)}>
                Reset
              </Button>
            )}
          </State>
          <State label="skipped" className="items-stretch">
            <ChoiceCard
              question="Which caption style?"
              choices={[
                { id: 'bold', label: 'Bold Pop' },
                { id: 'calm', label: 'Calm Serif' },
              ]}
              onChoose={() => {}}
              chosenId="skip"
            />
          </State>
        </div>
      </Specimen>

      <Specimen title="ResultMessage" note="Undo and Compare sit on the result. Errors: what happened, what is safe, one action.">
        <div className="space-y-8">
          <ResultMessage
            status="done"
            summary={undone ? 'Undone. The project is back to how it was.' : 'Done — 3 clips trimmed, captions added.'}
            changes={undone ? [] : ['Removed 42 seconds of silence', 'Added Bold Pop captions to 3 clips']}
            version={{
              name: 'Trimmed silences, added captions',
              undone,
              onUndo: () => setUndone(true),
              onRedo: () => setUndone(false),
              onCompare: () => toast.show({ title: 'Compare opens here' }),
            }}
            suggestions={SUGGESTIONS}
            onSuggestion={(text) => {
              setPrompt(text);
              toast.show({ title: 'Filled the prompt bar', description: text });
            }}
            details={{
              steps: runSteps(RUN_LABELS.length),
              operations: ['Cut 14 ranges from clip 1–3', 'Set caption style to Bold Pop', 'Moved clip 2 start to 0:03'],
            }}
            timestamp="Just now"
          />
          <ResultMessage
            status="partial"
            summary="Added B-roll to 2 of 3 clips."
            notDone={[{ label: 'Clip 3', reason: 'no library shots matched “city at night”' }]}
            version={{ name: 'Added B-roll', onUndo: () => {}, onCompare: () => {} }}
            suggestions={['Use “night street” instead']}
            onSuggestion={setPrompt}
          />
          <ResultMessage
            status="failed"
            summary="I could not read the audio in interview.mov."
            safeNote="Nothing was changed. Your earlier versions are untouched."
            onRetry={() => toast.show({ title: 'Trying again' })}
          />
        </div>
      </Specimen>
    </GallerySection>
  );
}
