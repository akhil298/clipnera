import { useState } from 'react'
import { mcp } from '../state/mcp'
import { useStore } from '../state/store'

function Snippet({ id, label, text }: { id: string; label: string; text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="snippet">
      <div className="snippet-head">
        <span>{label}</span>
        <button type="button" onClick={() => void navigator.clipboard.writeText(text).then(() => setCopied(true)).catch(() => undefined)}>{copied ? 'Copied' : 'Copy'}</button>
      </div>
      <pre id={id}>{text}</pre>
    </div>
  )
}

/** Connect Claude Code, Codex and other MCP agents on this Mac. */
export function AgentsSheet() {
  const { state, open } = useStore(mcp, (s) => s)
  if (!open || !state) return null
  const claude = `claude mcp add --transport http clipnera ${state.url} --header "Authorization: Bearer ${state.token}"`
  const codex = `[mcp_servers.clipnera]\ncommand = "node"\nargs = ["${state.bridge}"]`
  return (
    <div className="palette-backdrop" onPointerDown={() => mcp.set({ open: false })}>
      <div className="sheet" role="dialog" aria-label="Connect Claude Code or Codex" onPointerDown={(e) => e.stopPropagation()}>
        <h2>Connect Claude Code or Codex</h2>
        <label className="switch" htmlFor="mcp-on">
          <input id="mcp-on" type="checkbox" checked={state.enabled} onChange={(e) => void window.clipnera.mcp.setEnabled(e.target.checked)} />
          <span>Let agents on this Mac use Clipnera Studio</span>
        </label>
        <p className={state.error ? 'turn-failed' : 'muted'} role="status">
          {state.error ?? (state.listening ? `On, at ${state.url}` : 'Off')}
        </p>
        <p className="muted">
          Agents can read the project and footage, run the editor's commands (each one undoable, and shown in Activity under their name) and hand edits to Clipnera's AI. They can't export, publish, approve plans or sign in.
        </p>
        <Snippet id="mcp-claude" label="Claude Code (Terminal)" text={claude} />
        <Snippet id="mcp-codex" label="Codex (~/.codex/config.toml)" text={codex} />
        <p className="muted">The token stays on this Mac; the Codex bridge reads it from Clipnera Studio's settings.</p>
        <div className="sheet-actions"><button type="button" className="secondary" onClick={() => mcp.set({ open: false })}>Done</button></div>
      </div>
    </div>
  )
}
