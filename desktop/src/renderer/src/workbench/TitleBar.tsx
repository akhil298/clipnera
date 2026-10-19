import { runCommand } from '../commands'
import { exporting } from '../state/export'
import { project } from '../state/project'
import { useStore } from '../state/store'

const STAGES: Record<string, string> = { queued: 'Waiting to render', rendering: 'Rendering' }

function ExportStatus() {
  const state = useStore(exporting, (s) => s)
  switch (state.phase) {
    case 'rendering':
      return <span className="export-status">{STAGES[state.render?.status ?? 'queued'] ?? 'Rendering'}{state.render?.stage ? ` · ${state.render.stage}` : ''}…</span>
    case 'downloading':
      return <span className="export-status">Saving {Math.round(state.progress * 100)}%</span>
    case 'saved':
      return (
        <span className="export-status saved">
          Saved to Movies/Clipnera · <button type="button" onClick={() => runCommand('export.reveal')}>Show in Finder</button>
        </span>
      )
    case 'failed':
      return <span className="export-status failed" title={state.error ?? ''}>Export failed: {state.error}</span>
    default:
      return null
  }
}

export function TitleBar() {
  const title = useStore(project, (s) => s.project?.title ?? 'Clipnera Studio')
  const canExport = useStore(project, (s) => Boolean(s.timeline?.tracks.some((t) => t.items.length)))
  const busy = useStore(exporting, (s) => s.phase === 'rendering' || s.phase === 'downloading')
  return (
    <header className="titlebar">
      <span className="titlebar-project">{title}</span>
      <div className="titlebar-actions">
        <ExportStatus />
        <button type="button" className="export-button" disabled={!canExport || busy} title="Export video (⌘E)" onClick={() => runCommand('export.video')}>
          Export
        </button>
      </div>
    </header>
  )
}
