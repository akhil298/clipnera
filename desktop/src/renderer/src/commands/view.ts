import { VIEW_COMMANDS } from '../../../shared/commands'
import { BOTTOM_TABS, SIDE_VIEWS, type BottomTab, type LayoutState, type SideView } from '../state/layout'
import { palette } from '../state/palette'
import type { Store } from '../state/store'
import type { CommandRegistry } from './registry'

function oneOf<T extends string>(allowed: readonly T[], value: unknown, name: string): T {
  if (typeof value === 'string' && (allowed as readonly string[]).includes(value)) return value as T
  throw new Error(`${name} must be one of: ${allowed.join(', ')}`)
}

/** Layout commands. Returns a function that unregisters them. */
export function registerViewCommands(registry: CommandRegistry, layout: Store<LayoutState>): () => void {
  const toggle = (key: 'sideVisible' | 'bottomVisible' | 'aiVisible') => () => layout.set((s) => ({ [key]: !s[key] }))

  const disposers = [
    registry.register({
      id: VIEW_COMMANDS.palette,
      title: 'Show All Commands',
      category: 'View',
      description: 'Open the command palette to find and run any command.',
      shortcut: 'Mod+K',
      aiCanRun: false,
      run: () => palette.set(({ open }) => ({ open: !open }))
    }),
    registry.register<{ view: SideView }>({
      id: 'view.showSideView',
      needsArgs: true,
      title: 'Show Side Panel View',
      category: 'View',
      description: `Open the side panel on one view: ${SIDE_VIEWS.join(', ')}.`,
      aiCanRun: true,
      run: (args) => layout.set({ sideView: oneOf(SIDE_VIEWS, args?.view, 'view'), sideVisible: true })
    }),
    registry.register({
      id: VIEW_COMMANDS.toggleSidePanel,
      title: 'Toggle Side Panel',
      category: 'View',
      description: 'Show or hide the side panel (media, sounds, effects and the other library views).',
      shortcut: 'Mod+Alt+S',
      aiCanRun: true,
      run: toggle('sideVisible')
    }),
    registry.register<{ tab: BottomTab }>({
      id: 'view.showBottomTab',
      needsArgs: true,
      title: 'Show Bottom Panel Tab',
      category: 'View',
      description: `Open the bottom panel on one tab: ${BOTTOM_TABS.join(', ')}.`,
      aiCanRun: true,
      run: (args) => layout.set({ bottomTab: oneOf(BOTTOM_TABS, args?.tab, 'tab'), bottomVisible: true })
    }),
    registry.register({
      id: VIEW_COMMANDS.toggleBottomPanel,
      title: 'Toggle Bottom Panel',
      category: 'View',
      description: 'Show or hide the bottom panel with the activity log and problems.',
      shortcut: 'Mod+J',
      aiCanRun: true,
      run: toggle('bottomVisible')
    }),
    registry.register({
      id: VIEW_COMMANDS.toggleAiPanel,
      title: 'Toggle AI Panel',
      category: 'View',
      description: 'Show or hide the AI chat panel.',
      shortcut: 'Mod+Shift+A',
      aiCanRun: false,
      run: toggle('aiVisible')
    })
  ]

  return () => disposers.forEach((dispose) => dispose())
}
