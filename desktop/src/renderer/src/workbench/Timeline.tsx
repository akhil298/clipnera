import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { itemEnd, itemFrames, type Item, type Timeline as TimelineDoc, type Track } from '@timeline'
import { runCommand } from '../commands'
import { framingOf } from '../player/framing'
import { player } from '../player/player'
import { timelineSeconds } from '../player/sequence'
import { chat } from '../state/chat'
import { media } from '../state/media'
import { project } from '../state/project'
import { MAX_ZOOM, MIN_ZOOM, rangeLabel, timelineView, type TimeRange } from '../state/selection'
import { useStore } from '../state/store'

const LABELS: Record<Track['kind'], string> = { video: 'Video', overlay: 'Overlay', text: 'Text', audio: 'Audio', graphic: 'Graphics' }
const TICK_STEPS = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600]
const SNAP_PX = 8
const SPEEDS = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3, 4]
// Further than this is a range drag; less is a click that moves the playhead.
const DRAG_PX = 4

type DragMode = 'move' | 'trimStart' | 'trimEnd'
interface Drag {
  id: string
  mode: DragMode
  startX: number
  dx: number
}

function trackLabels(tracks: Track[]): string[] {
  const seen: Partial<Record<Track['kind'], number>> = {}
  return tracks.map((t) => `${LABELS[t.kind]} ${(seen[t.kind] = (seen[t.kind] ?? 0) + 1)}`)
}

function clockLabel(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(Math.floor(s)).padStart(2, '0')}${s % 1 ? '.5' : ''}`
}

function itemLabel(item: Item, t: TimelineDoc, names: Map<string, string>): string {
  switch (item.type) {
    case 'clip':
      return names.get(item.asset) ?? t.assets[item.asset]?.key.split('/').pop() ?? item.asset
    case 'text':
      return item.text
    case 'music':
      return `♪ ${item.track}`
    case 'sfx':
      return named(item.name)
    case 'graphic':
      return typeof item.extra.solid === 'string' ? 'Flash' : typeof item.extra.graphic === 'string' ? named(item.extra.graphic) : 'Graphic'
  }
}

/** A library id as a name: "glitch_bars" → "Glitch bars". */
const named = (id: string) => (id.charAt(0).toUpperCase() + id.slice(1)).replace(/_/g, ' ')
// Under this width an item drops its padding so its name still shows.
const NARROW_PX = 64

/** Where a dragged item would land, in frames, snapped to the playhead and other items' edges. */
function dropFrame(t: TimelineDoc, item: Item, dx: number, zoom: number, playhead: number): number {
  const fps = t.fps
  const raw = item.at + (dx / zoom) * fps
  const edges = [playhead * fps, ...t.tracks.flatMap((tr) => tr.items.filter((i) => i.id !== item.id).flatMap((i) => [i.at, itemEnd(i)]))]
  const length = itemFrames(item)
  const snapPx = (SNAP_PX / zoom) * fps
  for (const edge of edges) {
    if (Math.abs(raw - edge) < snapPx) return edge
    if (Math.abs(raw + length - edge) < snapPx) return edge - length
  }
  return Math.max(0, Math.round(raw))
}

/** Select & ask: the prompt bar that floats over a selected range. */
function RangeAsk({ range, left }: { range: TimeRange; left: number }) {
  const [draft, setDraft] = useState('')
  const send = () => {
    if (!draft.trim()) return
    runCommand('agent.send', { prompt: draft })
    setDraft('')
  }
  return (
    <form className="range-ask" style={{ left }} onPointerDown={(e) => e.stopPropagation()} onSubmit={(e) => (e.preventDefault(), send())}>
      <input
        id="range-ask"
        aria-label={`Ask the AI about ${rangeLabel(range)}`}
        placeholder={`Ask about ${rangeLabel(range)}…`}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
      />
      <button type="button" title="Play this part" onClick={() => runCommand('player.playRange', { from: range.start, to: range.end })}>▶</button>
      <button type="submit" disabled={!draft.trim()}>Ask</button>
      <button type="button" aria-label="Clear range" onClick={() => runCommand('timeline.clearRange')}>×</button>
    </form>
  )
}

function Toolbar({ t }: { t: TimelineDoc }) {
  const { selection } = useStore(timelineView, (s) => s)
  const { saving, error } = useStore(project, (s) => s)
  const selected = selection.length === 1 ? t.tracks.flatMap((tr) => tr.items).find((i) => i.id === selection[0]) : undefined
  const clip = selected?.type === 'clip' ? selected : undefined

  return (
    <div className="timeline-toolbar">
      <button type="button" title="Split at playhead (⌘B)" onClick={() => runCommand('timeline.split')}>Split</button>
      <button type="button" title="Delete (⌫)" disabled={!selection.length} onClick={() => runCommand('timeline.delete')}>Delete</button>
      <button type="button" title="Undo (⌘Z)" onClick={() => runCommand('edit.undo')}>Undo</button>
      <button type="button" title="Redo (⇧⌘Z)" onClick={() => runCommand('edit.redo')}>Redo</button>
      {clip && (
        <span className="timeline-clip-controls">
          <label htmlFor="clip-speed">Speed</label>
          <select id="clip-speed" value={clip.speed} onChange={(e) => runCommand('timeline.setSpeed', { item: clip.id, speed: Number(e.target.value) })}>
            {[...new Set([...SPEEDS, clip.speed])].sort((a, b) => a - b).map((s) => <option key={s} value={s}>{s}×</option>)}
          </select>
          <label htmlFor="clip-volume">Volume</label>
          <input id="clip-volume" type="range" min={0} max={2} step={0.05} value={clip.volume} onChange={(e) => runCommand('timeline.setVolume', { item: clip.id, volume: Number(e.target.value) })} />
        </span>
      )}
      <span className="timeline-status" role="status">{error ? <span className="failed">{error}</span> : saving ? 'Saving…' : 'Saved'}</span>
      <button type="button" title="Zoom out (⌘−)" onClick={() => runCommand('timeline.zoomOut')}>−</button>
      <button type="button" title="Zoom in (⌘=)" onClick={() => runCommand('timeline.zoomIn')}>+</button>
    </div>
  )
}

export function Timeline() {
  const t = useStore(project, (s) => s.timeline)
  const loading = useStore(project, (s) => s.loading)
  const { selection, zoom, range } = useStore(timelineView, (s) => s)
  const { time, mode, clipId } = useStore(player.state, (s) => s)
  const [sweep, setSweep] = useState<{ startX: number; left: number; from: number; to: number; moved: boolean } | null>(null)
  const items = useStore(media, (s) => s.items)
  const touched = useStore(chat, (s) => s.touched)
  const scroller = useRef<HTMLDivElement>(null)
  const [drag, setDrag] = useState<Drag | null>(null)
  const fitted = useRef(false)

  const length = t ? timelineSeconds(t) : 0
  // Fit the whole edit in view the first time there is something to show.
  useEffect(() => {
    if (fitted.current || !length || !scroller.current) return
    fitted.current = true
    const width = scroller.current.clientWidth - 100
    timelineView.set({ zoom: Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, width / (length * 1.05))) })
  }, [length])

  // Keep the playhead in view while it moves.
  const x = time * zoom
  useEffect(() => {
    const el = scroller.current
    if (!el) return
    if (x < el.scrollLeft || x > el.scrollLeft + el.clientWidth - 100) el.scrollLeft = Math.max(0, x - 40)
  }, [x])

  if (!t) {
    return (
      <section className="timeline" aria-label="Timeline">
        <p className="empty">{loading ? 'Opening your project…' : 'No project is open.'}</p>
      </section>
    )
  }

  const names = new Map(items.map((i) => [i.id, i.name]))
  const labels = trackLabels(t.tracks)
  const seconds = Math.max(length + 10, (scroller.current?.clientWidth ?? 1000) / zoom)
  const step = TICK_STEPS.find((s) => s * zoom >= 70) ?? 600
  const ticks = Array.from({ length: Math.floor(seconds / step) + 1 }, (_, i) => i * step)
  const empty = !t.tracks.some((tr) => tr.items.length)

  // On the ruler or an empty part of a track: a click moves the playhead, a drag selects a range.
  const startSweep = (event: ReactPointerEvent<HTMLElement>) => {
    const left = event.currentTarget.getBoundingClientRect().left
    const at = Math.max(0, (event.clientX - left) / zoom)
    event.currentTarget.setPointerCapture(event.pointerId)
    setSweep({ startX: event.clientX, left, from: at, to: at, moved: false })
  }
  const moveSweep = (event: ReactPointerEvent<HTMLElement>) => {
    if (!sweep) return
    const moved = sweep.moved || Math.abs(event.clientX - sweep.startX) > DRAG_PX
    setSweep({ ...sweep, moved, to: Math.max(0, (event.clientX - sweep.left) / zoom) })
  }
  const endSweep = (event: ReactPointerEvent<HTMLElement>) => {
    const done = sweep
    setSweep(null)
    if (!done) return
    if (done.moved) return runCommand('timeline.setRange', { from: done.from, to: done.to })
    if (mode !== 'timeline') runCommand('player.showTimeline')
    if (length) runCommand('player.seek', { seconds: done.from })
    if (!event.shiftKey) runCommand('timeline.select', { items: [] })
    if (range) runCommand('timeline.clearRange')
  }
  const sweepHandlers = { onPointerDown: startSweep, onPointerMove: moveSweep, onPointerUp: endSweep }
  const shown = sweep?.moved ? { start: Math.min(sweep.from, sweep.to), end: Math.max(sweep.from, sweep.to) } : range

  const startDrag = (event: ReactPointerEvent<HTMLElement>, item: Item, dragMode: DragMode) => {
    event.stopPropagation()
    event.currentTarget.setPointerCapture(event.pointerId)
    const ids = event.shiftKey ? (selection.includes(item.id) ? selection.filter((id) => id !== item.id) : [...selection, item.id]) : [item.id]
    if (ids.join() !== selection.join()) runCommand('timeline.select', { items: ids })
    setDrag({ id: item.id, mode: dragMode, startX: event.clientX, dx: 0 })
  }

  const finishDrag = (item: Item) => {
    const current = drag
    setDrag(null)
    if (!current || Math.abs(current.dx) < 3) return
    const frames = (current.dx / zoom) * t.fps
    if (current.mode === 'move') return runCommand('timeline.move', { item: item.id, at: dropFrame(t, item, current.dx, zoom, time) })
    if (item.type !== 'clip') return
    const sourceFrames = Math.round(frames * item.speed)
    runCommand('timeline.trim', current.mode === 'trimStart' ? { item: item.id, srcIn: item.src_in + sourceFrames } : { item: item.id, srcOut: item.src_out + sourceFrames })
  }

  const geometry = (item: Item) => {
    let left = (item.at / t.fps) * zoom
    let width = (itemFrames(item) / t.fps) * zoom
    if (drag?.id === item.id) {
      if (drag.mode === 'move') left = (dropFrame(t, item, drag.dx, zoom, time) / t.fps) * zoom
      if (drag.mode === 'trimStart') {
        left += drag.dx
        width -= drag.dx
      }
      if (drag.mode === 'trimEnd') width += drag.dx
    }
    return { left, width: Math.max(4, width) }
  }

  return (
    <section className="timeline" aria-label="Timeline">
      <Toolbar t={t} />
      <div className="timeline-scroll" ref={scroller}>
        <div className="timeline-canvas" style={{ width: seconds * zoom + 100 }}>
          <div className="timeline-ruler">
            <span className="lane-label" />
            <div className="ticks" {...sweepHandlers}>
              {ticks.map((s) => <span key={s} style={{ left: s * zoom }}>{clockLabel(s)}</span>)}
            </div>
          </div>
          {t.tracks.map((track, index) => (
            <div key={track.id} className="lane" role="group" aria-label={labels[index]}>
              <span className="lane-label">{labels[index]}</span>
              <div className="lane-track" {...sweepHandlers}>
                {track.items.map((item) => {
                  const { left, width } = geometry(item)
                  const selected = selection.includes(item.id)
                  return (
                    <div
                      key={item.id}
                      className={`item item-${item.type}${width < NARROW_PX ? ' narrow' : ''}${selected ? ' selected' : ''}${clipId === item.id ? ' playing' : ''}${touched.includes(item.id) ? ' touched' : ''}`}
                      style={{ left, width }}
                      role="button"
                      aria-label={`${itemLabel(item, t, names)} at ${clockLabel(item.at / t.fps)}`}
                      title={`${itemLabel(item, t, names)} · ${clockLabel(item.at / t.fps)}`}
                      aria-pressed={selected}
                      data-item={item.id}
                      onPointerDown={(e) => startDrag(e, item, 'move')}
                      onPointerMove={(e) => drag?.id === item.id && setDrag({ ...drag, dx: e.clientX - drag.startX })}
                      onPointerUp={() => finishDrag(item)}
                    >
                      {item.type === 'clip' && <span className="trim trim-start" aria-hidden="true" onPointerDown={(e) => startDrag(e, item, 'trimStart')} />}
                      <span className="item-label">{itemLabel(item, t, names)}</span>
                      {item.type === 'clip' && item.speed !== 1 && <span className="item-badge">{item.speed}×</span>}
                      {item.type === 'clip' && framingOf(item).zoom > 1.001 && <span className="item-badge" title="Zoomed in">⤢ {framingOf(item).zoom.toFixed(2)}</span>}
                      {item.type === 'clip' && <span className="trim trim-end" aria-hidden="true" onPointerDown={(e) => startDrag(e, item, 'trimEnd')} />}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
          {shown && (
            <div className="range-band" style={{ left: 84 + shown.start * zoom, width: (shown.end - shown.start) * zoom }} aria-label={`Selected range ${rangeLabel(shown)}`}>
              <span>{rangeLabel(shown)}</span>
            </div>
          )}
          {range && !sweep && <RangeAsk range={range} left={84 + range.start * zoom} />}
          {mode === 'timeline' && <div className="playhead" style={{ left: 84 + x }} aria-hidden="true" />}
          {empty && <p className="timeline-empty">Click + on a file in Media to put it on the timeline.</p>}
        </div>
      </div>
    </section>
  )
}
