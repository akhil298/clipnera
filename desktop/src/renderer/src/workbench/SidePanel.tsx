import type { ReactElement } from 'react'
import { layout, type SideView } from '../state/layout'
import { useStore } from '../state/store'
import { EffectsPanel } from './EffectsPanel'
import { MediaPanel } from './MediaPanel'
import { MusicPanel } from './MusicPanel'
import { RulesPanel } from './RulesPanel'
import { TakesPanel } from './TakesPanel'
import { SoundsPanel } from './SoundsPanel'
import { TextPanel } from './TextPanel'
import { SIDE_VIEW_INFO } from './sideViews'

const PANELS: Partial<Record<SideView, ReactElement>> = { media: <MediaPanel />, text: <TextPanel />, sounds: <SoundsPanel />, music: <MusicPanel />, effects: <EffectsPanel />, rules: <RulesPanel />, takes: <TakesPanel /> }

export function SidePanel() {
  const view = useStore(layout, (s) => s.sideView)
  const info = SIDE_VIEW_INFO[view]
  return (
    <aside className="sidepanel" aria-label={info.label}>
      <h2 className="panel-title">{info.label}</h2>
      {PANELS[view] ?? <p className="empty">{info.empty}</p>}
    </aside>
  )
}
