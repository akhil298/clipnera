import { useEffect, useState } from 'react'
import { CLAUDE_INSTALL_COMMAND, type ClaudeCodeStatus } from '../../../shared/ipc'
import { runCommand } from '../commands'
import { reason } from '../state/errors'
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

/**
 * The person's own Claude (Pro or Max) through Claude Code: Clipnera connects it to the editor and
 * opens it; signing in to Claude happens in Claude Code, on Anthropic's own page (Google works there).
 */
function UseClaude() {
  const mcpState = useStore(mcp, (s) => s.state)
  const [status, setStatus] = useState<ClaudeCodeStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const check = () => void window.clipnera.mcp.claudeStatus().then(setStatus).catch(() => setStatus(null))
  useEffect(check, [])
  const open = () => {
    setBusy(true)
    setMessage(null)
    window.clipnera.mcp
      .openClaude()
      .then((s) => setMessage(s.signedIn ? 'Claude Code is open in Terminal and connected: ask it to edit, and watch the timeline.' : 'Claude Code is open in Terminal: sign in there with your Claude account (Google works), then ask it to edit.'))
      .catch((e: unknown) => setMessage(reason(e)))
      .finally(() => {
        setBusy(false)
        check()
      })
  }
  const line = !status
    ? 'Looking for Claude Code on this Mac…'
    : !status.installed
      ? 'Claude Code isn’t installed on this Mac.'
      : status.signedIn
        ? `Claude Code ${status.version ?? ''} · signed in${status.authMethod === 'claude.ai' ? ' with your Claude plan' : ''}`
        : `Claude Code ${status.version ?? ''} · not signed in yet`
  return (
    <section className="use-claude" aria-label="Use your Claude">
      <h3>Use your Claude (Pro or Max)</h3>
      <p className="muted">Edit with your own Claude plan: Claude Code drives Clipnera Studio, and every change shows here and can be undone.</p>
      <p role="status">{line}</p>
      {status?.installed ? (
        <button type="button" className="primary" disabled={busy} onClick={open}>{busy ? 'Opening…' : 'Open in Claude Code'}</button>
      ) : status ? (
        <>
          <Snippet id="claude-install" label="Install Claude Code (Terminal)" text={CLAUDE_INSTALL_COMMAND} />
          <div className="sheet-actions">
            <button type="button" className="secondary" onClick={() => void window.clipnera.mcp.installClaude()}>Install in Terminal</button>
            <button type="button" className="secondary" onClick={check}>Check again</button>
          </div>
        </>
      ) : null}
      {message && <p className="muted" role="status">{message}</p>}
      {mcpState?.claudeChatAvailable && status?.installed && (
        <label className="switch" htmlFor="claude-chat">
          <input id="claude-chat" type="checkbox" checked={mcpState.claudeChat}
            onChange={(e) => void window.clipnera.mcp.setClaudeChat(e.target.checked)} />
          <span>Also use my Claude in Clipnera’s chat: pick “My Claude” in the chat’s model menu (personal · beta)</span>
        </label>
      )}
    </section>
  )
}

/** The person's own Anthropic API key, for Claude in Clipnera's chat on their own Anthropic account. */
function OwnKey() {
  const [state, setState] = useState<{ saved: boolean; last4: string | null } | null>(null)
  const [draft, setDraft] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  useEffect(() => void window.clipnera.mcp.claudeKey().then(setState), [])
  const done = (next: { saved: boolean; last4: string | null }, note: string) => {
    setState(next)
    setDraft('')
    setMessage(note)
    runCommand('agent.reloadModels')
  }
  return (
    <section className="use-claude" aria-label="Your Anthropic API key">
      <h3>Claude in Clipnera’s chat, on your Anthropic API key</h3>
      <p className="muted">Billed by Anthropic to your API account (console.anthropic.com), not your Pro/Max plan. The key stays encrypted on this Mac and goes with each chat turn only.</p>
      {state?.saved ? (
        <div className="sheet-actions">
          <span>Saved · ends in {state.last4}</span>
          <button type="button" className="secondary" onClick={() => void window.clipnera.mcp.clearClaudeKey().then((s) => done(s, 'Removed.'))}>Remove</button>
        </div>
      ) : (
        <form className="sheet-actions" onSubmit={(e) => {
          e.preventDefault()
          window.clipnera.mcp.setClaudeKey(draft).then((s) => done(s, 'Saved: pick a Claude “(my API key)” model in the chat.')).catch((err: unknown) => setMessage(reason(err)))
        }}>
          <input id="anthropic-key" type="password" aria-label="Anthropic API key" placeholder="sk-ant-…" autoComplete="off" value={draft} onChange={(e) => setDraft(e.target.value)} />
          <button type="submit" className="secondary" disabled={!draft.trim()}>Save</button>
        </form>
      )}
      {message && <p className="muted" role="status">{message}</p>}
    </section>
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
        <UseClaude />
        <OwnKey />
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
