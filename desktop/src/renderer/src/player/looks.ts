/**
 * The render's colour looks (backend/edit_engine/looks.py) as colour matrices for the viewer.
 * Each FFmpeg filter becomes the same arithmetic on RGB in 0–1: colorbalance's shadow/highlight
 * shift per channel (s·(1−x) + h·x, a gain and an offset), then eq's saturation (around luma),
 * contrast (around mid grey) and brightness. Vignettes are drawn separately.
 */

type Rgb = [number, number, number]
interface Look {
  balance?: { shadows: Rgb; highlights: Rgb }
  saturation?: number
  contrast?: number
  brightness?: number
  vignette?: boolean
}

const LOOKS: Record<string, Look> = {
  natural: { contrast: 1.03, saturation: 1.05 },
  clean_bright: { brightness: 0.03, contrast: 1.05, saturation: 1.08 },
  warm_film: { balance: { shadows: [0.05, 0.01, -0.06], highlights: [0.04, 0, -0.05] }, contrast: 1.06, saturation: 0.95 },
  teal_orange: { balance: { shadows: [-0.06, 0, 0.08], highlights: [0.08, 0.01, -0.07] }, contrast: 1.08, saturation: 1.1 },
  moody: { contrast: 1.12, brightness: -0.03, saturation: 0.8, vignette: true },
  vivid: { contrast: 1.08, saturation: 1.3 },
  bw_punch: { saturation: 0, contrast: 1.25 }
}
export const DEFAULT_LOOK = 'natural'

/** A 4×5 colour matrix (rows R, G, B, A; columns R, G, B, A, offset), as feColorMatrix takes it. */
export type Matrix = number[][]

const IDENTITY: Matrix = [
  [1, 0, 0, 0, 0],
  [0, 1, 0, 0, 0],
  [0, 0, 1, 0, 0],
  [0, 0, 0, 1, 0]
]

/** b then a: the matrix applying `first`, then `then`. */
function compose(then: Matrix, first: Matrix): Matrix {
  return then.map((row) => [0, 1, 2, 3, 4].map((col) => {
    const linear = [0, 1, 2, 3].reduce((sum, k) => sum + row[k] * first[k][col], 0)
    return col === 4 ? linear + row[4] : linear
  }))
}

const LUMA = [0.2126, 0.7152, 0.0722]

function saturationMatrix(s: number): Matrix {
  return [0, 1, 2].map((r) => [...[0, 1, 2].map((c) => LUMA[c] * (1 - s) + (r === c ? s : 0)), 0, 0]).concat([[0, 0, 0, 1, 0]])
}

export function lookMatrix(name: string): Matrix {
  const look = LOOKS[name] ?? LOOKS[DEFAULT_LOOK]
  let m = IDENTITY
  if (look.balance) {
    const { shadows, highlights } = look.balance
    // out = x + s·(1 − x) + h·x = x·(1 + h − s) + s
    m = compose([0, 1, 2].map((c) => [...[0, 1, 2].map((k) => (k === c ? 1 + highlights[c] - shadows[c] : 0)), 0, shadows[c]]).concat([[0, 0, 0, 1, 0]]), m)
  }
  if (look.saturation !== undefined) m = compose(saturationMatrix(look.saturation), m)
  const contrast = look.contrast ?? 1
  const offset = 0.5 * (1 - contrast) + (look.brightness ?? 0)
  m = compose([0, 1, 2].map((c) => [...[0, 1, 2].map((k) => (k === c ? contrast : 0)), 0, offset]).concat([[0, 0, 0, 1, 0]]), m)
  return m
}

export const hasVignette = (name: string) => Boolean((LOOKS[name] ?? LOOKS[DEFAULT_LOOK]).vignette)

/** Applies a matrix to one colour (for tests and swatches). */
export function apply(m: Matrix, rgb: Rgb): Rgb {
  return [0, 1, 2].map((r) => Math.min(1, Math.max(0, m[r][0] * rgb[0] + m[r][1] * rgb[1] + m[r][2] * rgb[2] + m[r][4]))) as Rgb
}

export const matrixValues = (m: Matrix) => m.flat().map((v) => +v.toFixed(5)).join(' ')
