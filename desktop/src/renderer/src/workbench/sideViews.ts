import type { SideView } from '../state/layout'
import type { IconName } from './Icon'

export interface SideViewInfo {
  label: string
  icon: IconName
  /** What the panel will hold once it's built, and the phase that builds it. */
  empty: string
}

export const SIDE_VIEW_INFO: Record<SideView, SideViewInfo> = {
  media: { label: 'Media', icon: 'media', empty: 'Your footage, images and audio. Importing arrives in phase 3.' },
  search: { label: 'Search footage', icon: 'search', empty: 'Find moments by what is said or shown. Arrives with the backend link in phase 7.' },
  sounds: { label: 'Sounds', icon: 'sounds', empty: 'Sound effects library.' },
  effects: { label: 'Effects', icon: 'effects', empty: 'Zoom and framing.' },
  text: { label: 'Text & Captions', icon: 'text', empty: 'Caption styles, titles and callouts.' },
  music: { label: 'Music', icon: 'music', empty: 'Music for the edit.' },
  rules: { label: 'Edit Rules', icon: 'rules', empty: 'What the AI always follows in this project.' },
  skills: { label: 'Skills', icon: 'skills', empty: 'Saved recipes like /podcast-clean. Arrives in v1.1.' },
  takes: { label: 'Takes', icon: 'takes', empty: 'Versions of your edit to compare and go back to.' }
}
