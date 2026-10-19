import { useCallback, useEffect, useRef, useState } from 'react'
import { runCommand } from '../commands'
import { player } from '../player/player'
import { placement } from '../player/framing'
import { hasVignette } from '../player/looks'
import { formatTimecode } from '../player/time'
import { project } from '../state/project'
import { timelineView } from '../state/selection'
import { useStore } from '../state/store'
import { Icon } from './Icon'
import { LookFilters } from './LookFilters'
import { Layers } from './Layers'
import { Overlay } from './Overlay'
import { PointAsk } from './PointAsk'

// Stable across renders: a new ref function each render would detach the element mid-playback.
const attachMedia = (el: HTMLVideoElement | null) => player.attach(el)
const clamp01 = (v: number) => Math.min(1, Math.max(0, v))
const attachMix = (el: HTMLDivElement | null) => player.attachMix(el)

function Speed({ speed }: { speed: number }) {
  if (speed === 0 || speed === 1) return null
  return <span className="viewer-speed">{speed < 0 ? '◀◀' : '▶▶'} {Math.abs(speed)}×</span>
}

export function Viewer() {
  const { mode, item, time, duration, speed, gap, framing } = useStore(player.state, (s) => s)
  const hasTimeline = useStore(project, (s) => Boolean(s.timeline?.tracks.some((t) => t.items.length)))
  const shape = useStore(project, (s) => (s.timeline ? `${s.timeline.width} / ${s.timeline.height}` : '16 / 9'))
  const look = useStore(project, (s) => s.timeline?.look ?? 'natural')
  const point = useStore(timelineView, (s) => s.point)
  const picture = useRef<HTMLVideoElement | null>(null)
  // Stable: a new ref function each render would detach the picture mid-playback.
  const attachPicture = useCallback((el: HTMLVideoElement | null) => {
    picture.current = el
    attachMedia(el)
  }, [])
  // The overlay is sized to the picture, so captions scale with it as the render's do.
  const frame = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const [height, setHeight] = useState(0)
  const [source, setSource] = useState({ w: 0, h: 0 })
  useEffect(() => {
    const el = frame.current
    if (!el) return
    const observer = new ResizeObserver(() => {
      setWidth(el.clientWidth)
      setHeight(el.clientHeight)
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  const fps = player.fps
  // The edit is cropped and zoomed like the export; a single file shows whole.
  const framed = framing && source.w && width && height ? placement(source.w, source.h, width, height, framing) : null
  const playing = speed !== 0
  const ready = mode === 'source' ? Boolean(item) : duration > 0

  return (
    <section className="viewer" aria-label="Viewer">
      <div
        className="viewer-frame"
        ref={frame}
        style={{ aspectRatio: mode === 'timeline' ? shape : undefined }}
        onClick={(e) => {
          // Point & ask: a click on the edit's picture points at that spot.
          if (mode !== 'timeline' || gap || !picture.current) return
          const box = e.currentTarget.getBoundingClientRect()
          const shown = picture.current.getBoundingClientRect()
          runCommand('point.set', { x: clamp01((e.clientX - box.left) / box.width), y: clamp01((e.clientY - box.top) / box.height), sourceX: clamp01((e.clientX - shown.left) / shown.width) })
        }}
      >
        <video
          ref={attachPicture}
          preload="auto"
          playsInline
          aria-label="Viewer picture"
          className={`${gap ? 'hidden-picture' : ''}${framed ? ' framed' : ''}`}
          style={{
            ...(framed ? { left: framed.left, top: framed.top, width: framed.width, height: framed.height } : {}),
            // The edit wears its look, like the export; a single file shows as shot.
            filter: mode === 'timeline' ? `url(#viewer-look-${look})` : undefined
          }}
          onLoadedMetadata={(e) => setSource({ w: e.currentTarget.videoWidth, h: e.currentTarget.videoHeight })}
        />
        {mode === 'source' && item?.kind === 'audio' && <div className="viewer-audio"><Icon name="music" size={28} /><span>{item.name}</span></div>}
        {mode === 'timeline' && !hasTimeline && <p className="viewer-note">Put footage on the timeline to see your edit here</p>}
        {mode === 'source' && item && (
          <button type="button" className="viewer-mode" onClick={() => runCommand('player.showTimeline')}>
            Viewing {item.name} · Back to timeline <kbd>Esc</kbd>
          </button>
        )}
        <LookFilters ids={[look]} prefix="viewer-look-" />
        {mode === 'timeline' && hasVignette(look) && <div className="vignette" aria-hidden="true" />}
        <Layers />
        <Overlay width={width} />
        <div className="audio-mix" ref={attachMix} aria-hidden="true" />
        {mode === 'timeline' && point && <PointAsk point={point} />}
        <Speed speed={speed} />
      </div>
      <input
        id="scrubber"
        className="scrubber"
        type="range"
        aria-label="Playhead"
        min={0}
        max={duration || 0}
        step={1 / fps}
        value={Math.min(time, duration || 0)}
        disabled={!ready}
        onChange={(e) => runCommand('player.seek', { seconds: Number(e.target.value) })}
      />
      <div className="transport">
        <span className="timecode" aria-label="Playhead time">{formatTimecode(time, fps)}</span>
        <div className="transport-buttons">
          <button type="button" aria-label="Previous frame" title="Previous frame (←)" disabled={!ready} onClick={() => runCommand('player.stepBack')}><Icon name="back" size={16} /></button>
          <button type="button" aria-label={playing ? 'Pause' : 'Play'} title="Play / Pause (Space)" disabled={!ready} onClick={() => runCommand('player.togglePlay')}>
            <Icon name={playing ? 'pause' : 'play'} size={16} />
          </button>
          <button type="button" aria-label="Next frame" title="Next frame (→)" disabled={!ready} onClick={() => runCommand('player.stepForward')}><Icon name="forward" size={16} /></button>
        </div>
        <span className="timecode muted" aria-label="Duration">{formatTimecode(duration, fps)}</span>
      </div>
    </section>
  )
}
