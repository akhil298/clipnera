import { runCommand } from '../commands'
import { VIEW_COMMANDS } from '../../../shared/commands'
import { layout, SIDE_VIEWS, type SideView } from '../state/layout'
import { useStore } from '../state/store'
import { Icon } from './Icon'
import { SIDE_VIEW_INFO } from './sideViews'

export function ActivityBar() {
  const { sideView, sideVisible } = useStore(layout, (s) => s)

  // Clicking the open view closes the panel, like VS Code.
  const open = (view: SideView) =>
    view === sideView && sideVisible ? runCommand(VIEW_COMMANDS.toggleSidePanel) : runCommand('view.showSideView', { view })

  return (
    <nav className="activitybar" aria-label="Views">
      {SIDE_VIEWS.map((view) => (
        <button
          key={view}
          type="button"
          className="activitybar-item"
          aria-label={SIDE_VIEW_INFO[view].label}
          aria-pressed={sideVisible && sideView === view}
          title={SIDE_VIEW_INFO[view].label}
          onClick={() => open(view)}
        >
          <Icon name={SIDE_VIEW_INFO[view].icon} />
        </button>
      ))}
    </nav>
  )
}
