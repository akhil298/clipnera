import { toFrames } from '@timeline'
import { runCommand } from '../commands'
import { targetClip, ZOOMS } from '../commands/effects'
import { framingOf } from '../player/framing'
import { player } from '../player/player'
import { media } from '../state/media'
import { project } from '../state/project'
import { timelineView } from '../state/selection'
import { useStore } from '../state/store'
import { LookFilters } from './LookFilters'

const ZOOM_LABELS: Record<keyof typeof ZOOMS, string> = { none: 'None', punch: 'Punch-in', tight: 'Tight' }

function Looks() {
  const looks = useStore(project, (s) => s.looks)
  const current = useStore(project, (s) => s.timeline?.look)
  if (!looks.length) return <p className="muted">Colour looks come from your Clipnera account; sign in to pick one.</p>
  return (
    <section aria-label="Look">
      <h3 className="panel-subtitle">Look</h3>
      <LookFilters ids={looks.map((l) => l.id)} prefix="swatch-look-" />
      <div className="look-grid">
        {looks.map((look) => (
          <button key={look.id} type="button" className="look-tile" aria-pressed={current === look.id} onClick={() => runCommand('look.set', { look: look.id })}>
            <span className="look-swatch" style={{ filter: `url(#swatch-look-${look.id})` }} />
            {look.label}
          </button>
        ))}
      </div>
    </section>
  )
}

export function EffectsPanel() {
  return (
    <div className="library-panel effects-panel">
      <Looks />
      <ClipEffects />
    </div>
  )
}

function ClipEffects() {
  const timeline = useStore(project, (s) => s.timeline)
  const time = useStore(player.state, (s) => s.time)
  useStore(timelineView, (s) => s.selection)
  const names = useStore(media, (s) => s.items)
  const clip = timeline ? targetClip(timeline, toFrames(time * timeline.fps)) : null
  if (!clip) return <p className="muted">Select a clip, or put the playhead over one, to zoom or reframe it.</p>
  const framing = framingOf(clip)
  const name = names.find((i) => i.id === clip.asset)?.name ?? 'Clip'

  return (
    <>
      <p className="muted">{name} at {((clip.at / (timeline?.fps ?? 30))).toFixed(1)} s</p>
      <section aria-label="Zoom">
        <h3 className="panel-subtitle">Zoom</h3>
        <div className="segmented">
          {(Object.keys(ZOOMS) as (keyof typeof ZOOMS)[]).map((key) => (
            <button key={key} type="button" aria-pressed={Math.abs(framing.zoom - ZOOMS[key]) < 0.005} onClick={() => runCommand('effects.zoom', { item: clip.id, scale: ZOOMS[key] })}>
              {ZOOM_LABELS[key]} {ZOOMS[key]}×
            </button>
          ))}
        </div>
        <input id="effect-zoom" aria-label="Zoom amount" type="range" min={1} max={2} step={0.01} value={framing.zoom} onChange={(e) => runCommand('effects.zoom', { item: clip.id, scale: Number(e.target.value) })} />
      </section>
      <section aria-label="Framing">
        <h3 className="panel-subtitle">Framing</h3>
        <input id="effect-frame" aria-label="Framing, left to right" type="range" min={0} max={1} step={0.01} value={framing.x} onChange={(e) => runCommand('effects.frame', { item: clip.id, x: Number(e.target.value) })} />
        <div className="range-ends muted"><span>Left</span><span>Right</span></div>
      </section>
      <p className="muted">Looks, zooms (moving ones too), framing, speed and flashes are in exports. Fades, slides and shakes on the main track show on the timeline but aren't drawn in exports yet.</p>
    </>
  )
}
