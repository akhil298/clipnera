import type { ClipItem, Keyframe } from '@timeline'

export interface Framing {
  zoom: number
  /** Where the crop is centred across the source, 0–1. */
  x: number
}

const mean = (values: number[]) => values.reduce((a, b) => a + b, 0) / values.length

const EASES: Record<Keyframe['ease'], (p: number) => number> = {
  linear: (p) => p,
  in: (p) => p * p,
  out: (p) => p * (2 - p),
  in_out: (p) => (p < 0.5 ? 2 * p * p : 1 - 2 * (1 - p) * (1 - p))
}

/**
 * A keyframed value at frame `f` of its item, as the export moves it (backend edit_engine/keyframes.py):
 * held before the first point and after the last, and between two points following the ease of
 * the point it moves towards.
 */
export function valueAt(points: Keyframe[], f: number): number {
  const sorted = [...points].sort((a, b) => a.f - b.f)
  if (f <= sorted[0].f) return sorted[0].v
  const next = sorted.findIndex((k) => k.f > f)
  if (next < 0) return sorted[sorted.length - 1].v
  const [from, to] = [sorted[next - 1], sorted[next]]
  return from.v + (to.v - from.v) * EASES[to.ease]((f - from.f) / (to.f - from.f))
}

/** A clip's typical framing, for showing in panels: a zoom that moves is given at its average, never below 1. */
export function framingOf(clip: Pick<ClipItem, 'transform' | 'keyframes'>): Framing {
  const scale = clip.keyframes.scale
  const x = clip.keyframes.x
  return { zoom: Math.max(1, scale?.length ? mean(scale.map((k) => k.v)) : clip.transform.scale), x: x?.length ? mean(x.map((k) => k.v)) : clip.transform.x }
}

/** A clip's framing at frame `f` of it, as the export draws it there: never below 1×, the centre kept within the source. */
export function framingAt(clip: Pick<ClipItem, 'transform' | 'keyframes'>, f: number): Framing {
  const { scale, x } = clip.keyframes
  return {
    zoom: Math.max(1, scale?.length ? valueAt(scale, f) : clip.transform.scale),
    x: Math.min(1, Math.max(0, x?.length ? valueAt(x, f) : clip.transform.x))
  }
}

export interface Placement {
  left: number
  top: number
  width: number
  height: number
}

/**
 * Where to draw a source picture of `iw`×`ih` inside a `w`×`h` frame so the frame shows exactly
 * the render's crop (edit_engine/render.py): the widest window of the frame's shape that fits,
 * divided by the zoom, centred at x (kept inside the picture), its top at 45% of the spare height.
 */
export function placement(iw: number, ih: number, w: number, h: number, framing: Framing): Placement {
  const cw = Math.min(iw, (ih * w) / h) / framing.zoom
  const ch = (cw * h) / w
  const k = w / cw
  const cropLeft = Math.min(Math.max(framing.x * iw - cw / 2, 0), iw - cw)
  const cropTop = (ih - ch) * 0.45
  return { left: -cropLeft * k, top: -cropTop * k, width: iw * k, height: ih * k }
}
