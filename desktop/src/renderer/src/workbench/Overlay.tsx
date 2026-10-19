import { useMemo } from 'react'
import type { CaptionLook, PreviewText } from '../../../shared/api'
import { captionLines, lineAt } from '../player/captions'
import { player } from '../player/player'
import { project } from '../state/project'
import { useStore } from '../state/store'

/** The renderer's title kinds (edit_engine/render.py TEXT_STYLES): size as a share of width, y as a share of height. */
const TITLE: Record<PreviewText['kind'], { size: number; y: number; color: string; plate: boolean }> = {
  hook: { size: 0.11, y: 0.22, color: '#FFD700', plate: true },
  pop: { size: 0.13, y: 0.4, color: '#FFFFFF', plate: false },
  line: { size: 0.06, y: 0.7, color: '#FFFFFF', plate: true }
}

function Captions({ look, width, time }: { look: CaptionLook; width: number; time: number }) {
  const words = useStore(project, (s) => s.preview?.words ?? [])
  const lines = useMemo(() => captionLines(words, look.max_words_per_line), [words, look.max_words_per_line])
  const now = lineAt(lines, time)
  if (!now) return null
  // Templates are sized for a 1080-wide frame, like the ASS generator scales them.
  const size = (look.font_size * width) / 1080
  return (
    <p
      className="overlay-caption"
      aria-label="Caption"
      style={{
        top: `${look.position_y * 100}%`,
        fontFamily: `'${look.font_family}', sans-serif`,
        fontSize: size,
        color: look.font_color,
        textTransform: look.uppercase ? 'uppercase' : 'none',
        WebkitTextStroke: look.stroke_color && look.stroke_width ? `${size * 0.09}px ${look.stroke_color}` : undefined,
        background: look.background && look.background_color ? look.background_color : undefined
      }}
    >
      {now.line.words.map((w, i) => (
        <span key={`${w.start}`} style={i === now.active ? { color: look.highlight_color } : undefined}>
          {w.word}{' '}
        </span>
      ))}
    </p>
  )
}

/** What the export draws over the picture, drawn the same way: captions and titles. */
export function Overlay({ width }: { width: number }) {
  const preview = useStore(project, (s) => s.preview)
  const { time, mode } = useStore(player.state, (s) => s)
  if (mode !== 'timeline' || !preview || !width) return null
  const titles = preview.texts.filter((t) => time >= t.at && time < t.at + t.dur)
  return (
    <div className="overlay" aria-hidden="false">
      {titles.map((t) => {
        const style = TITLE[t.kind]
        return (
          <p
            key={`${t.at}-${t.text}`}
            className={`overlay-title${style.plate ? ' plate' : ''}`}
            aria-label="Title"
            style={{ top: `${style.y * 100}%`, fontSize: style.size * width, color: style.color, textTransform: t.kind === 'line' ? 'none' : 'uppercase' }}
          >
            {t.text}
          </p>
        )
      })}
      {preview.caption_look && <Captions look={preview.caption_look} width={width} time={time} />}
    </div>
  )
}
