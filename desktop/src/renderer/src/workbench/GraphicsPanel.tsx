import { useEffect } from 'react'
import { runCommand } from '../commands'
import { graphics, loadGraphics } from '../state/graphics'
import { useStore } from '../state/store'

/** The animated graphics shelf: light leaks, glitches, confetti… each drawn in code, with its moods. */
export function GraphicsPanel() {
  // Select the stored object itself: a new array per read would re-render without end.
  const shelf = Object.values(useStore(graphics, (s) => s.byId))
  useEffect(() => void loadGraphics(), [])
  return (
    <div className="library-panel">
      {shelf.length === 0 && <p className="empty">Loading the graphics…</p>}
      <ul className="library-list" aria-label="Graphics">
        {shelf.map((graphic) => (
          <li key={graphic.id}>
            <span className="library-name">
              {graphic.name}
              <span className="muted"> · {graphic.seconds.toFixed(1)} s · {graphic.moods.join(', ')}</span>
            </span>
            <button type="button" className="library-add" aria-label={`Add ${graphic.name} at the playhead`} onClick={() => runCommand('graphics.add', { id: graphic.id })}>+</button>
          </li>
        ))}
      </ul>
      <p className="muted">Drawn over the picture where the playhead is, in the viewer and the export.</p>
    </div>
  )
}
