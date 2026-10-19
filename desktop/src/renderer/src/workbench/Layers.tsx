import { useEffect, useRef } from 'react'
import { layersAt, type Layer } from '../player/layers'
import { player } from '../player/player'
import { graphics, loadGraphics } from '../state/graphics'
import { project } from '../state/project'
import { useStore } from '../state/store'

// A layer's own video is put back on time when it drifts further than this.
const DRIFT = 0.25

/** Keeps a layer's video at `target` seconds: playing along with the edit, or still on the frame. */
function useSynced(ref: React.RefObject<HTMLVideoElement | null>, target: number, playing: boolean, rate: number) {
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const sync = () => {
      if (playing) {
        el.playbackRate = rate
        if (Math.abs(el.currentTime - target) > DRIFT) el.currentTime = target
        if (el.paused) void el.play().catch(() => undefined)
      } else {
        el.pause()
        if (Math.abs(el.currentTime - target) > 0.02) el.currentTime = target
      }
    }
    // A seek before the file has loaded is dropped: do it again once it has.
    if (el.readyState < 1) el.addEventListener('loadedmetadata', sync, { once: true })
    else sync()
    return () => el.removeEventListener('loadedmetadata', sync)
  }, [ref, target, playing, rate])
}

const VERTEX = `attribute vec2 p; varying vec2 uv; void main() { uv = vec2((p.x + 1.0) / 2.0, (1.0 - p.y) / 2.0); gl_Position = vec4(p, 0.0, 1.0); }`
// Colour from the left half, the matte from the right, cropped to cover the frame like the export.
const FRAGMENT = `precision mediump float; varying vec2 uv; uniform sampler2D tex; uniform vec2 crop;
void main() {
  vec2 c = vec2(0.5) + (uv - vec2(0.5)) * crop;
  vec3 colour = texture2D(tex, vec2(c.x * 0.5, c.y)).rgb;
  float alpha = texture2D(tex, vec2(0.5 + c.x * 0.5, c.y)).r;
  gl_FragColor = vec4(colour * alpha, alpha);
}`

function program(gl: WebGLRenderingContext): WebGLProgram {
  const shader = (type: number, source: string) => {
    const s = gl.createShader(type)!
    gl.shaderSource(s, source)
    gl.compileShader(s)
    return s
  }
  const p = gl.createProgram()!
  gl.attachShader(p, shader(gl.VERTEX_SHADER, VERTEX))
  gl.attachShader(p, shader(gl.FRAGMENT_SHADER, FRAGMENT))
  gl.linkProgram(p)
  return p
}

/** A packed-alpha graphic (colour left, matte right), drawn with its transparency over the picture. */
function GraphicLayer({ url, offset, playing }: { url: string; offset: number; playing: boolean }) {
  const video = useRef<HTMLVideoElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  useSynced(video, offset, playing, 1)
  useEffect(() => {
    const el = canvas.current
    const source = video.current
    const gl = el?.getContext('webgl', { premultipliedAlpha: true, alpha: true, preserveDrawingBuffer: true })
    if (!el || !source || !gl) return
    const p = program(gl)
    gl.useProgram(p)
    const buffer = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW)
    const at = gl.getAttribLocation(p, 'p')
    gl.enableVertexAttribArray(at)
    gl.vertexAttribPointer(at, 2, gl.FLOAT, false, 0, 0)
    const texture = gl.createTexture()
    gl.bindTexture(gl.TEXTURE_2D, texture)
    for (const [k, v] of [[gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE], [gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR]]) gl.texParameteri(gl.TEXTURE_2D, k, v)
    // Drawn whenever the video shows a new frame (playing, or after a seek), not on a timer:
    // animation frames stop in a window the system thinks is hidden.
    const draw = () => {
      if (source.readyState < 2 || !source.videoWidth) return
      el.width = el.clientWidth * devicePixelRatio
      el.height = el.clientHeight * devicePixelRatio
      gl.viewport(0, 0, el.width, el.height)
      // Cover the frame: the graphic's own shape is half the file's width.
      const graphicShape = source.videoWidth / 2 / source.videoHeight
      const frameShape = el.width / el.height
      gl.uniform2f(gl.getUniformLocation(p, 'crop'), frameShape > graphicShape ? 1 : frameShape / graphicShape, frameShape > graphicShape ? graphicShape / frameShape : 1)
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, source)
      gl.clearColor(0, 0, 0, 0)
      gl.clear(gl.COLOR_BUFFER_BIT)
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)
    }
    let callback = 0
    const onFrame = () => {
      draw()
      callback = source.requestVideoFrameCallback(onFrame)
    }
    callback = source.requestVideoFrameCallback(onFrame)
    const events = ['loadeddata', 'seeked'] as const
    events.forEach((e) => source.addEventListener(e, draw))
    const resized = new ResizeObserver(draw)
    resized.observe(el)
    draw()
    return () => {
      source.cancelVideoFrameCallback(callback)
      events.forEach((e) => source.removeEventListener(e, draw))
      resized.disconnect()
    }
  }, [url])
  return (
    <>
      <video ref={video} src={url} crossOrigin="anonymous" muted playsInline preload="auto" className="layer-source" />
      <canvas ref={canvas} className="layer layer-graphic" data-layer="graphic" />
    </>
  )
}

/** B-roll or a still over the picture: filling the frame, or picture-in-picture under scale 1. */
function PictureLayer({ layer, playing }: { layer: Extract<Layer, { kind: 'video' | 'image' }>; playing: boolean }) {
  const video = useRef<HTMLVideoElement>(null)
  useSynced(video, layer.sourceTime, playing, layer.speed)
  const url = player.assetUrl(layer.asset)
  if (!url) return null
  const small = layer.scale < 1
  const style = small
    ? { width: `${layer.scale * 100}%`, height: `${layer.scale * 100}%`, left: `${(layer.x - layer.scale / 2) * 100}%`, top: `${(layer.y - layer.scale / 2) * 100}%`, opacity: layer.opacity }
    : { inset: 0, opacity: layer.opacity }
  return layer.kind === 'image'
    ? <img src={url} alt="" className="layer layer-picture" data-layer="image" style={style} />
    : <video ref={video} src={url} muted playsInline preload="auto" className="layer layer-picture" data-layer="video" style={style} />
}

/** Everything the export draws over the main picture, drawn the same way in the viewer. */
export function Layers() {
  const time = useStore(player.state, (s) => s.time)
  const playing = useStore(player.state, (s) => s.speed === 1)
  const mode = useStore(player.state, (s) => s.mode)
  const timeline = useStore(project, (s) => s.timeline)
  const shelf = useStore(graphics, (s) => s.byId)
  const layers = timeline && mode === 'timeline' ? layersAt(timeline, time) : []
  const usesShelf = useStore(project, (s) => Boolean(s.timeline?.tracks.some((t) => t.items.some((i) => i.type === 'graphic' && typeof i.extra.graphic === 'string'))))
  useEffect(() => {
    if (usesShelf) void loadGraphics()
  }, [usesShelf])
  return (
    <div className="layers" aria-label="Layers">
      {layers.map((layer) => {
        if (layer.kind === 'solid') return <div key={layer.id} className="layer" data-layer="solid" style={{ inset: 0, background: layer.colour, opacity: layer.opacity }} />
        if (layer.kind === 'graphic') {
          const graphic = shelf[layer.graphic]
          // Like the export, a graphic plays once: past its own length it's gone.
          return graphic && layer.offset < graphic.seconds ? <GraphicLayer key={layer.id} url={graphic.url} offset={layer.offset} playing={playing} /> : null
        }
        return <PictureLayer key={layer.id} layer={layer} playing={playing} />
      })}
    </div>
  )
}
