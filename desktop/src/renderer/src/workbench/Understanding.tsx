import type { MediaItem } from '../../../shared/media'
import { runCommand } from '../commands'
import { project } from '../state/project'
import { useStore } from '../state/store'

const STAGES: Record<string, string> = {
  shots: 'looking at the shots',
  transcript: 'listening to what is said',
  music: 'finding the beat',
  reading: 'working out what happens'
}

const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`

/** What the AI has understood about a file, under its row in Media. */
export function Understanding({ item }: { item: MediaItem }) {
  const analysis = useStore(project, (s) => s.analysis[item.id])
  if (!analysis || item.status !== 'ready') return null

  if (analysis.status === 'pending' || analysis.status === 'running') {
    return <p className="understanding working">AI is {STAGES[analysis.stage ?? ''] ?? 'getting ready to look'}…</p>
  }
  if (analysis.status === 'failed') {
    return (
      <p className="understanding failed">
        The AI couldn't read this file{analysis.error ? `: ${analysis.error}` : '.'}{' '}
        <button type="button" onClick={() => void window.clipnera.project.retryAnalysis(item.id)}>Try again</button>
      </p>
    )
  }
  const found = analysis.findings
  if (!found) return null
  const counts = [found.words && `${found.words} words`, found.fillers && `${found.fillers} fillers`, found.shots && `${found.shots} shots`, found.tempo_bpm && `${Math.round(found.tempo_bpm)} bpm`].filter(Boolean)

  return (
    <div className="understanding" aria-label={`What the AI found in ${item.name}`}>
      {found.summary && <p className="understanding-summary">{found.summary}</p>}
      {counts.length > 0 && <p className="muted">{counts.join(' · ')}</p>}
      {found.chapters?.length > 0 && (
        <ul className="moments" aria-label="What happens">
          {found.chapters.map((m) => (
            <li key={`${m.t0}`}>
              <button
                type="button"
                title="Play this part"
                onClick={() => {
                  runCommand('player.open', { id: item.id })
                  runCommand('player.playRange', { from: m.t0, to: m.t1 })
                }}
              >
                <span className="moment-time">{clock(m.t0)}</span> {m.text}
              </button>
            </li>
          ))}
        </ul>
      )}
      {found.problems.map((p) => <p key={p} className="understanding failed">{p}</p>)}
    </div>
  )
}
