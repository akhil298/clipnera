import { useState } from 'react'
import { runCommand } from '../commands'
import type { PointedSpot } from '../state/selection'

/** Point & ask: the marker on the spot and what can be done about it. */
export function PointAsk({ point }: { point: PointedSpot }) {
  const [draft, setDraft] = useState('')
  const below = point.y < 0.6
  return (
    <>
      <span className="point-marker" style={{ left: `${point.x * 100}%`, top: `${point.y * 100}%` }} aria-hidden="true" />
      <form
        className="point-ask"
        style={{ left: `${Math.min(Math.max(point.x * 100, 22), 78)}%`, top: `${point.y * 100}%`, transform: `translate(-50%, ${below ? '18px' : 'calc(-100% - 18px)'})` }}
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault()
          if (!draft.trim()) return
          runCommand('agent.send', { prompt: draft })
          setDraft('')
        }}
      >
        <input id="point-ask" aria-label="Ask the AI about this spot" placeholder="Ask about this spot…" value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus />
        <button type="button" onClick={() => runCommand('effects.zoomHere')}>Zoom in here</button>
        <button type="submit" disabled={!draft.trim()}>Ask</button>
        <button type="button" aria-label="Clear the spot" onClick={() => runCommand('point.clear')}>×</button>
      </form>
    </>
  )
}
