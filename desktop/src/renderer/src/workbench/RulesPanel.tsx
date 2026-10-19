import { useState } from 'react'
import { runCommand } from '../commands'
import { rules } from '../state/rules'
import { useStore } from '../state/store'

const EXAMPLES = ['Never cut the guest mid-sentence', 'Captions: Hype style, max 3 words', 'Keep the intro under 10 seconds']

export function RulesPanel() {
  const { list, learned } = useStore(rules, (s) => s)
  const [draft, setDraft] = useState('')
  const add = (text: string) => {
    if (!text.trim()) return
    runCommand('rules.add', { text })
    setDraft('')
  }
  return (
    <div className="library-panel rules-panel">
      <p className="muted">Plain rules the AI follows on every request in this project, unless you ask otherwise.</p>
      <form className="title-add" onSubmit={(e) => (e.preventDefault(), add(draft))}>
        <input id="rule-text" aria-label="New rule" placeholder="e.g. Never cut the guest mid-sentence" value={draft} maxLength={200} onChange={(e) => setDraft(e.target.value)} />
        <button type="submit" className="secondary" disabled={!draft.trim()}>Add</button>
      </form>
      {list.length === 0 ? (
        <ul className="rule-examples">{EXAMPLES.map((e) => <li key={e}><button type="button" onClick={() => add(e)}>+ {e}</button></li>)}</ul>
      ) : (
        <ol className="rule-list" aria-label="Edit Rules">
          {list.map((rule, i) => (
            <li key={rule}>
              <span>{rule}</span>
              <button type="button" aria-label={`Remove rule: ${rule}`} onClick={() => runCommand('rules.remove', { index: i })}>×</button>
            </li>
          ))}
        </ol>
      )}
      <section aria-label="Learned from you">
        <h3 className="panel-subtitle">Learned from your edits</h3>
        {learned.length === 0 ? (
          <p className="muted">Nothing yet. When you change what the AI made, it learns your taste here.</p>
        ) : (
          <ul className="rule-list">
            {learned.map((p) => (
              <li key={p.key}>
                <span>{p.label}: {p.value}{p.in_use ? '' : <span className="muted"> (still learning)</span>}</span>
                <button type="button" aria-label={`Forget ${p.label}`} onClick={() => runCommand('rules.forget', { key: p.key })}>×</button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
