import { createStore } from './store'

export const SIDE_VIEWS = ['media', 'search', 'sounds', 'effects', 'text', 'music', 'rules', 'skills', 'takes'] as const
export type SideView = (typeof SIDE_VIEWS)[number]

export const BOTTOM_TABS = ['activity', 'problems'] as const
export type BottomTab = (typeof BOTTOM_TABS)[number]

export interface LayoutState {
  sideView: SideView
  sideVisible: boolean
  bottomTab: BottomTab
  bottomVisible: boolean
  aiVisible: boolean
}

export const DEFAULT_LAYOUT: LayoutState = {
  sideView: 'media',
  sideVisible: true,
  bottomTab: 'activity',
  bottomVisible: true,
  aiVisible: true
}

export const layout = createStore<LayoutState>(DEFAULT_LAYOUT)
