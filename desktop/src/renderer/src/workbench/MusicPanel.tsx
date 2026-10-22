import { useEffect, useRef, useState } from 'react'
import type { LibraryMusic } from '../../../shared/api'
import { commands, runCommand } from '../commands'
import { reason } from '../state/errors'
import { media } from '../state/media'
import { project } from '../state/project'
import { useStore } from '../state/store'

const db = (volume: number) => (volume > 0 ? `${(20 * Math.log10(volume)).toFixed(0)} dB` : 'off')

/** Clipnera's own music beds (composed in code): hear one, lay it under the edit. */
function MusicShelf() {
  const [tracks, setTracks] = useState<LibraryMusic[]>([])
  const [error, setError] = useState<string | null>(null)
  const [adding, setAdding] = useState<string | null>(null)
  const preview = useRef<HTMLAudioElement | null>(null)
  useEffect(() => {
    window.clipnera.project.music('').then(setTracks).catch((e: unknown) => setError(reason(e)))
    return () => preview.current?.pause()
  }, [])
  const play = (track: LibraryMusic) => {
    preview.current?.pause()
    preview.current = new Audio(track.url)
    void preview.current.play().catch(() => undefined)
  }
  const use = (track: LibraryMusic) => {
    setAdding(track.id)
    commands.execute('music.addTrack', { id: track.id }).catch((e: unknown) => setError(reason(e))).finally(() => setAdding(null))
  }
  return (
    <section aria-label="Clipnera music">
      <h3 className="panel-subtitle">Clipnera music</h3>
      {error && <p className="empty">{error}</p>}
      <ul className="library-list" aria-label="Music shelf">
        {tracks.map((track) => (
          <li key={track.id}>
            <button type="button" className="library-play" aria-label={`Play ${track.name}`} onClick={() => play(track)}>▶</button>
            <span className="library-name">
              {track.name}
              <span className="muted"> · {track.mood} · {Math.round(track.bpm)} bpm · {Math.round(track.seconds)} s</span>
            </span>
            <button type="button" className="secondary" aria-label={`Use ${track.name} as music`} disabled={adding === track.id} onClick={() => use(track)}>
              {adding === track.id ? '…' : 'Use'}
            </button>
          </li>
        ))}
      </ul>
      <p className="muted">Made by Clipnera, safe to post anywhere. It plays on to the end of the edit.</p>
    </section>
  )
}

export function MusicPanel() {
  const timeline = useStore(project, (s) => s.timeline)
  const items = useStore(media, (s) => s.items)
  const audio = items.filter((i) => i.kind === 'audio' && i.status === 'ready')
  const music = timeline?.tracks.find((t) => t.id === 'music')?.items.filter((i) => i.type === 'clip') ?? []
  const names = new Map(items.map((i) => [i.id, i.name]))

  return (
    <div className="library-panel">
      {music.length > 0 && (
        <section aria-label="Music in the edit">
          {music.map((clip) =>
            clip.type === 'clip' ? (
              <div key={clip.id} className="music-now">
                <span className="library-name">{names.get(clip.asset) ?? (typeof clip.extra.name === 'string' ? clip.extra.name : 'Music')}</span>
                <label htmlFor={`music-${clip.id}`} className="muted">Level {db(clip.volume)}</label>
                <input id={`music-${clip.id}`} type="range" min={0} max={1} step={0.01} value={clip.volume} onChange={(e) => runCommand('timeline.setVolume', { item: clip.id, volume: Number(e.target.value) })} />
              </div>
            ) : null
          )}
          <p className="muted">It ducks under speech in the export, and in the viewer.</p>
        </section>
      )}
      <MusicShelf />
      {audio.length === 0 ? (
        <p className="empty">Import a music file (MP3, M4A, WAV) and pick it here to lay it under the edit.</p>
      ) : (
        <ul className="library-list" aria-label="Music files">
          {audio.map((item) => (
            <li key={item.id}>
              <span className="library-name">{item.name}</span>
              <button type="button" className="secondary" onClick={() => runCommand('music.add', { mediaId: item.id })}>Use as music</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
