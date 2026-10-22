import { useEffect, useState } from 'react'
import type { LibraryBroll } from '../../../shared/api'
import { commands } from '../commands'
import { reason } from '../state/errors'

const SEARCH_DELAY_MS = 250

/** The public-domain B-roll shelf (mostly NASA): search it, preview a shot, put it over the edit. */
export function BrollPanel() {
  const [query, setQuery] = useState('')
  const [shots, setShots] = useState<LibraryBroll[]>([])
  const [error, setError] = useState<string | null>(null)
  const [adding, setAdding] = useState<string | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => {
      window.clipnera.project
        .broll(query)
        .then((found) => {
          setShots(found)
          setError(null)
        })
        .catch((e: unknown) => setError(reason(e)))
    }, SEARCH_DELAY_MS)
    return () => clearTimeout(timer)
  }, [query])

  const add = (shot: LibraryBroll) => {
    setAdding(shot.id)
    // Copying the shot into the project takes a moment: show it, and say so if it fails.
    commands.execute('broll.add', { id: shot.id, title: shot.title }).catch((e: unknown) => setError(reason(e))).finally(() => setAdding(null))
  }

  return (
    <div className="library-panel">
      <input id="broll-search" className="library-search" aria-label="Search B-roll" placeholder="Search B-roll: rocket, earth, lab…" value={query} onChange={(e) => setQuery(e.target.value)} />
      {error && <p className="empty">{error}</p>}
      {!error && shots.length === 0 && <p className="empty">No shots found. The shelf is public-domain footage, mostly NASA.</p>}
      <ul className="library-list broll-list" aria-label="B-roll">
        {shots.map((shot) => (
          <li key={shot.id}>
            <video className="broll-thumb" src={`${shot.url}#t=0.5`} muted playsInline preload="metadata" onMouseEnter={(e) => void e.currentTarget.play().catch(() => undefined)} onMouseLeave={(e) => e.currentTarget.pause()} />
            <span className="library-name" title={shot.credit}>
              {shot.title}
              <span className="muted"> · {shot.seconds.toFixed(1)} s · {shot.credit}</span>
            </span>
            <button type="button" className="library-add" aria-label={`Add ${shot.title} at the playhead`} disabled={adding === shot.id} onClick={() => add(shot)}>
              {adding === shot.id ? '…' : '+'}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
