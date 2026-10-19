import { useState } from 'react'
import type { CaptionStyleOption } from '../../../shared/api'
import { runCommand } from '../commands'
import { TITLE_PLACES, type TitlePlace } from '../commands/captions'
import { media } from '../state/media'
import { project } from '../state/project'
import { useStore } from '../state/store'
import { mainVideoTrack } from '../timeline/edits'

const PLACES: Record<TitlePlace, string> = { top: 'Top', middle: 'Middle', lower: 'Lower third' }
const placeOf = (y: number): TitlePlace => (y < 0.35 ? 'top' : y > 0.6 ? 'lower' : 'middle')

function StyleTile({ option, current }: { option: CaptionStyleOption; current: boolean }) {
  const { look } = option
  return (
    <button type="button" className={`style-tile${current ? ' current' : ''}`} aria-pressed={current} title={option.description} onClick={() => runCommand('captions.setStyle', { style: option.id })}>
      <span
        className="style-sample"
        style={{ fontFamily: `'${look.font_family}', sans-serif`, color: look.font_color, textTransform: look.uppercase ? 'uppercase' : 'none', WebkitTextStroke: look.stroke_color ? `1px ${look.stroke_color}` : undefined, background: look.background ? (look.background_color ?? undefined) : undefined }}
      >
        Most <span style={{ color: look.highlight_color }}>never</span>
      </span>
      <span className="style-name">{option.name}</span>
    </button>
  )
}

/** Burned-in subtitles in the footage under the captions, from the media scan. */
function useOnScreenText(): string[] | null {
  const timeline = useStore(project, (s) => s.timeline)
  const items = useStore(media, (s) => s.items)
  const used = new Set(mainVideoTrack(timeline ?? ({ tracks: [] } as never))?.items.map((i) => (i.type === 'clip' ? i.asset : '')) ?? [])
  const found = items.filter((i) => used.has(i.id) && (i.onScreenText?.share ?? 0) >= 0.1)
  return found.length ? found.flatMap((i) => i.onScreenText?.examples ?? []).slice(0, 2) : null
}

export function TextPanel() {
  const timeline = useStore(project, (s) => s.timeline)
  const styles = useStore(project, (s) => s.captionStyles)
  const [draft, setDraft] = useState('')
  const onScreen = useOnScreenText()
  if (!timeline) return <p className="empty">Open a project to add captions and titles.</p>

  const captions = timeline.captions
  const on = captions?.enabled ?? false
  const titles = timeline.tracks.flatMap((t) => t.items).filter((i) => i.type === 'text').sort((a, b) => a.at - b.at)

  return (
    <div className="text-panel">
      <section aria-label="Captions">
        <label className="switch" htmlFor="captions-on">
          <input id="captions-on" type="checkbox" checked={on} onChange={() => runCommand('captions.toggle')} />
          <span>Captions</span>
        </label>
        {on && onScreen && (
          <p className="text-warning" role="alert">
            This footage already has words on screen in places{onScreen[0] ? ` (“${onScreen[0]}”)` : ''}. Captions may cover them.{' '}
            <button type="button" onClick={() => runCommand('captions.toggle')}>Turn captions off</button>
          </p>
        )}
        {styles.length > 0 ? (
          <div className="style-grid" aria-label="Caption styles">
            {styles.map((option) => <StyleTile key={option.id} option={option} current={on && captions?.style === option.id} />)}
          </div>
        ) : (
          <p className="muted">Caption styles come from your Clipnera account; sign in to pick one.</p>
        )}
      </section>

      <section aria-label="Titles">
        <h3 className="panel-subtitle">Titles</h3>
        <form className="title-add" onSubmit={(e) => {
          e.preventDefault()
          if (!draft.trim()) return
          runCommand('text.add', { text: draft })
          setDraft('')
        }}>
          <input id="title-text" aria-label="Title text" placeholder="Title at the playhead…" value={draft} maxLength={200} onChange={(e) => setDraft(e.target.value)} />
          <button type="submit" className="secondary" disabled={!draft.trim()}>Add</button>
        </form>
        <ul className="title-list">
          {titles.map((item) =>
            item.type === 'text' ? (
              <li key={item.id}>
                <input aria-label={`Words of title at ${(item.at / timeline.fps).toFixed(1)} s`} defaultValue={item.text} maxLength={200} onBlur={(e) => e.target.value.trim() && e.target.value !== item.text && runCommand('text.edit', { item: item.id, text: e.target.value })} onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()} />
                <select aria-label="Where the title sits" value={placeOf(item.transform.y)} onChange={(e) => runCommand('text.place', { item: item.id, place: e.target.value })}>
                  {(Object.keys(TITLE_PLACES) as TitlePlace[]).map((p) => <option key={p} value={p}>{PLACES[p]}</option>)}
                </select>
              </li>
            ) : null
          )}
        </ul>
      </section>
    </div>
  )
}
