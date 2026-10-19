import { useState } from 'react'
import { duration } from '@timeline'
import { runCommand } from '../commands'
import { project } from '../state/project'
import { useStore } from '../state/store'
import { takes } from '../state/takes'

const length = (frames: number, fps: number) => {
  const s = Math.round(frames / fps)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export function TakesPanel() {
  const list = useStore(takes, (s) => s.list)
  const timeline = useStore(project, (s) => s.timeline)
  const [name, setName] = useState('')
  const [confirm, setConfirm] = useState<string | null>(null)
  if (!timeline) return <p className="empty">Open a project to keep versions of its edit.</p>
  const now = duration(timeline)

  return (
    <div className="library-panel takes-panel">
      <form className="title-add" onSubmit={(e) => {
        e.preventDefault()
        runCommand('takes.save', { name: name || `Take ${list.filter((t) => t.source === 'manual').length + 1}` })
        setName('')
      }}>
        <input id="take-name" aria-label="Take name" placeholder="Name this version…" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
        <button type="submit" className="secondary">Save</button>
      </form>
      <p className="muted">Now: {length(now, timeline.fps)} · {timeline.tracks.reduce((n, t) => n + t.items.length, 0)} items. A take is also saved before each AI request.</p>
      {list.length === 0 ? (
        <p className="empty">No takes yet.</p>
      ) : (
        <ul className="take-list" aria-label="Takes">
          {list.map((take) => {
            const frames = duration(take.timeline)
            const diff = Math.round((frames - now) / timeline.fps)
            return (
              <li key={take.id} className={`take-${take.source}`}>
                <div className="take-head">
                  <span className="library-name">{take.name}</span>
                  <span className="muted">{new Date(take.savedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
                <span className="muted">
                  {length(frames, take.timeline.fps)} ({diff === 0 ? 'same length' : `${diff > 0 ? '+' : ''}${diff} s`}) · {take.timeline.tracks.reduce((n, t) => n + t.items.length, 0)} items · {take.timeline.look}
                </span>
                {confirm === take.id ? (
                  <div className="take-actions">
                    <span className="muted">Replace the timeline? Undo brings it back.</span>
                    <button type="button" className="problem-fix" onClick={() => (setConfirm(null), runCommand('takes.restore', { id: take.id }))}>Restore</button>
                    <button type="button" onClick={() => setConfirm(null)}>Cancel</button>
                  </div>
                ) : (
                  <div className="take-actions">
                    <button type="button" onClick={() => setConfirm(take.id)}>Restore…</button>
                    <button type="button" aria-label={`Delete take ${take.name}`} onClick={() => runCommand('takes.remove', { id: take.id })}>Delete</button>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
