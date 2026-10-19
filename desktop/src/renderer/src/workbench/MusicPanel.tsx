import { runCommand } from '../commands'
import { media } from '../state/media'
import { project } from '../state/project'
import { useStore } from '../state/store'

const db = (volume: number) => (volume > 0 ? `${(20 * Math.log10(volume)).toFixed(0)} dB` : 'off')

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
                <span className="library-name">{names.get(clip.asset) ?? 'Music'}</span>
                <label htmlFor={`music-${clip.id}`} className="muted">Level {db(clip.volume)}</label>
                <input id={`music-${clip.id}`} type="range" min={0} max={1} step={0.01} value={clip.volume} onChange={(e) => runCommand('timeline.setVolume', { item: clip.id, volume: Number(e.target.value) })} />
              </div>
            ) : null
          )}
          <p className="muted">It ducks under speech in the export, and in the viewer.</p>
        </section>
      )}
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
