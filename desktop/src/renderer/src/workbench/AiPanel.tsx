import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import type { PlanCard } from '../../../shared/agent'
import { runCommand } from '../commands'
import { pickModel } from '../commands/agent'
import { chat, type Turn } from '../state/chat'
import { teamOf } from '../state/team'
import { voice } from '../state/voice'
import { rangeLabel, timelineView } from '../state/selection'
import { useStore } from '../state/store'
import { Icon } from './Icon'

const EXAMPLES = ['Edit the video, keep it tight', 'Remove the pauses and filler words', 'Add captions', 'Add a zoom on the key moments']
const STEP_MARK = { pending: '○', running: '●', done: '✓', failed: '✕', skipped: '–' } as const

const send = (prompt: string) => runCommand('agent.send', { prompt })
const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`

function Plan({ plan }: { plan: PlanCard }) {
  const [busy, setBusy] = useState(false)
  const act = (run: () => Promise<unknown>) => {
    setBusy(true)
    void run().finally(() => setBusy(false))
  }
  return (
    <div className="plan-card" aria-label={`Plan: ${plan.title}`}>
      <div className="plan-head">
        <strong>{plan.title}</strong>
        <span className={`plan-status plan-${plan.status}`}>{plan.status}</span>
      </div>
      <p>{plan.summary}</p>
      {plan.result_line && <p className="muted">{plan.result_line}</p>}
      {plan.outline.length > 0 && (
        <ol className="plan-outline" aria-label="The edit, part by part">
          {plan.outline.map((part) => (
            <li key={part.start}>
              <span className="plan-outline-time">{clock(part.start)}–{clock(part.end)}</span>
              <span>
                {part.said && <span className="plan-outline-said">{part.said}</span>}
                <span className="muted">{part.actions.length ? part.actions.join(' · ') : 'Kept as it is'}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
      <div className="plan-team" aria-label="Agent team">
        {teamOf(plan.steps).map((lane) => (
          <section key={lane.member} className={`team-lane team-${lane.state}`} aria-label={`${lane.member}: ${lane.done} of ${lane.steps.length} done`}>
            <div className="team-head">
              <strong>{lane.member}</strong>
              <span className="muted">{lane.state === 'working' ? 'working' : lane.state === 'failed' ? 'stuck' : lane.state === 'done' ? 'done' : 'waiting'} · {lane.done}/{lane.steps.length}</span>
            </div>
            <ol className="plan-steps">
              {lane.steps.map((s) => (
                <li key={s.id} className={`step-${s.status}`}>
                  <span aria-hidden="true">{STEP_MARK[s.status]}</span> {s.intent}
                  {s.note && <span className="muted"> — {s.note}</span>}
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
      {plan.warnings.map((w) => <p key={w} className="plan-warning">{w}</p>)}
      {plan.error && <p className="plan-warning">{plan.error}</p>}
      {plan.status === 'proposed' && (
        <div className="plan-actions">
          <button type="button" className="primary" disabled={busy} onClick={() => act(() => window.clipnera.agent.approve(plan.id))}>
            Approve · up to {plan.credits} credits
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={() => act(() => window.clipnera.agent.reject(plan.id))}>Reject</button>
        </div>
      )}
    </div>
  )
}

function TurnView({ turn }: { turn: Turn }) {
  return (
    <li className="turn">
      <p className="turn-prompt">
        {turn.scope && <span className="scope-chip">{turn.scope}</span>}
        {turn.prompt}
      </p>
      <div className="turn-reply" aria-label="AI reply">
        {turn.tools.length > 0 && (
          <ul className="turn-tools">
            {turn.tools.map((t) => (
              <li key={t.id} className={`tool-${t.status}`}>
                <span aria-hidden="true">{t.status === 'running' ? '●' : t.status === 'ok' ? '✓' : '✕'}</span> {t.label}
                {t.error && <span className="muted"> — {t.error}</span>}
              </li>
            ))}
          </ul>
        )}
        {turn.todos.length > 0 && (
          <ul className="turn-todos" aria-label="To-do">
            {turn.todos.map((t) => <li key={t.text} className={`todo-${t.status}`}><span aria-hidden="true">{t.status === 'done' ? '☑' : t.status === 'active' ? '◐' : '☐'}</span> {t.text}</li>)}
          </ul>
        )}
        {turn.text.map((p, i) => <p key={i}>{p}</p>)}
        {turn.edits.length > 0 && (
          <div className="turn-edits">
            {turn.edits.map((e) => (
              <span key={e.undoStepId} className="edit-chip">
                {e.label}
                {e.undone ? (
                  <span className="muted"> · undone</span>
                ) : (
                  <button type="button" onClick={() => runCommand('agent.undoStep', { step: e.undoStepId })}>Undo</button>
                )}
              </span>
            ))}
          </div>
        )}
        {turn.plan && <Plan plan={turn.plan} />}
        {turn.ask && (
          <div className="turn-ask">
            <p>{turn.ask.question}</p>
            <div>{turn.ask.options.map((o) => <button key={o} type="button" className="secondary" onClick={() => send(o)}>{o}</button>)}</div>
          </div>
        )}
        {turn.status === 'working' && turn.tools.every((t) => t.status !== 'running') && <p className="muted thinking">Thinking…</p>}
        {turn.note && <p className={turn.status === 'failed' ? 'turn-failed' : 'muted'}>{turn.note}</p>}
      </div>
    </li>
  )
}

export function AiPanel() {
  const { turns, running, models, model, auto, unavailable } = useStore(chat, (s) => s)
  const range = useStore(timelineView, (s) => s.range)
  const [draft, setDraft] = useState('')
  const end = useRef<HTMLDivElement>(null)

  // A block body: in newer Chromium scrollIntoView returns a promise, which React would take for a cleanup.
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [turns])

  // A voice note lands in the composer, to read before sending.
  const { state: listening, heard, error: voiceError } = useStore(voice, (s) => s)
  useEffect(() => {
    if (heard) setDraft((d) => (d.trim() ? `${d.trim()} ${heard.text}` : heard.text))
  }, [heard])

  const submit = () => {
    if (!draft.trim() || running) return
    send(draft)
    setDraft('')
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <aside className="aipanel" aria-label="AI panel">
      <header className="aipanel-head">
        <Icon name="spark" size={16} />
        <span>Clipnera Agent</span>
        {models && (
          <select id="ai-model" aria-label="AI model" value={model ?? ''} onChange={(e) => pickModel(e.target.value)}>
            {models.models.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        )}
        <label className="aipanel-auto" title="Auto: never ask, and run whole edits without waiting for approval">
          <input id="ai-auto" type="checkbox" checked={auto} onChange={(e) => chat.set({ auto: e.target.checked })} /> Auto
        </label>
      </header>
      {running && <p className="aipanel-banner" role="status">AI is editing · press Esc to stop</p>}
      <div className="aipanel-body">
        {unavailable ? (
          <p className="empty">{unavailable}</p>
        ) : turns.length === 0 ? (
          <>
            <p className="aipanel-hello">Tell me what to edit.</p>
            <ul className="examples">{EXAMPLES.map((e) => <li key={e}><button type="button" onClick={() => send(e)}>{e}</button></li>)}</ul>
          </>
        ) : (
          <ol className="turns" aria-label="Conversation">{turns.map((t) => <TurnView key={t.id} turn={t} />)}</ol>
        )}
        <div ref={end} />
      </div>
      <form className="composer" onSubmit={(e) => (e.preventDefault(), submit())}>
        {range && (
          <div className="composer-scope">
            <span className="scope-chip">About {rangeLabel(range)}</span>
            <button type="button" aria-label="Ask about the whole video instead" onClick={() => runCommand('timeline.clearRange')}>×</button>
          </div>
        )}
        <textarea id="composer" aria-label="Message the AI" placeholder={unavailable ? '' : 'Describe an edit…'} rows={3} value={draft} disabled={Boolean(unavailable)} onChange={(e) => setDraft(e.target.value)} onKeyDown={onKeyDown} />
        <div className="composer-foot">
          <button
            type="button"
            className={`voice-button voice-${listening}`}
            aria-label={listening === 'recording' ? 'Stop the voice note' : 'Speak a request'}
            title="Voice note (⇧⌘V)"
            disabled={Boolean(unavailable) || listening === 'reading'}
            onClick={() => runCommand('voice.toggle')}
          >
            {listening === 'recording' ? '■' : '🎙'}
          </button>
          <span className="muted">{voiceError ?? (listening === 'recording' ? 'Listening… click to stop' : listening === 'reading' ? 'Reading what you said…' : running ? 'Esc stops the AI' : 'Enter to send · Shift+Enter for a new line')}</span>
          {running ? (
            <button type="button" className="stop" aria-label="Stop" onClick={() => runCommand('agent.stop')}>■</button>
          ) : (
            <button type="submit" aria-label="Send" disabled={!draft.trim() || Boolean(unavailable)}><Icon name="send" size={16} /></button>
          )}
        </div>
      </form>
    </aside>
  )
}
