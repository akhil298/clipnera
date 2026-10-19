import { useEffect, useRef, useState } from 'react'
import type { LibrarySound } from '../../../shared/api'
import { runCommand } from '../commands'
import { reason } from '../state/errors'

const SEARCH_DELAY_MS = 250

export function SoundsPanel() {
  const [query, setQuery] = useState('')
  const [sounds, setSounds] = useState<LibrarySound[]>([])
  const [error, setError] = useState<string | null>(null)
  const preview = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => {
      window.clipnera.project
        .sounds(query)
        .then((found) => {
          setSounds(found)
          setError(null)
        })
        .catch((e: unknown) => setError(reason(e)))
    }, SEARCH_DELAY_MS)
    return () => clearTimeout(timer)
  }, [query])

  const play = (sound: LibrarySound) => {
    preview.current?.pause()
    preview.current = new Audio(sound.url)
    void preview.current.play().catch(() => undefined)
  }

  return (
    <div className="library-panel">
      <input id="sound-search" className="library-search" aria-label="Search sounds" placeholder="Search sounds: whoosh, pop, ding…" value={query} onChange={(e) => setQuery(e.target.value)} />
      {error && <p className="empty">{error}</p>}
      {!error && sounds.length === 0 && <p className="empty">No sounds found.</p>}
      <ul className="library-list" aria-label="Sounds">
        {sounds.map((sound) => (
          <li key={sound.id}>
            <button type="button" className="library-play" aria-label={`Play ${sound.name}`} onClick={() => play(sound)}>▶</button>
            <span className="library-name">
              {sound.name}
              <span className="muted"> · {sound.seconds.toFixed(1)} s · {sound.category}</span>
            </span>
            <button type="button" className="library-add" aria-label={`Add ${sound.name} at the playhead`} onClick={() => runCommand('sounds.add', { id: sound.id, url: sound.url, seconds: sound.seconds })}>+</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
