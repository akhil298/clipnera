import { runCommand } from '../commands'
import { auth } from '../state/auth'
import { chat } from '../state/chat'
import { useAppInfo } from '../state/appInfo'
import { mcp } from '../state/mcp'
import { useStore } from '../state/store'

const credits = new Intl.NumberFormat('en-IN')

function Account() {
  const state = useStore(auth, (s) => s.state)
  if (state.status !== 'signedIn') return <span>Not signed in</span>
  const { user } = state
  return (
    <span className="statusbar-account">
      <span title={user.email}>{user.name}</span>
      <span className="statusbar-plan">{user.plan}</span>
      <span>{credits.format(user.ai_credits_minutes_remaining)} credits</span>
      {user.id !== 'preview' && <button type="button" onClick={() => runCommand('account.signOut')}>Sign out</button>}
    </span>
  )
}

function AgentState() {
  const running = useStore(chat, (s) => s.running)
  const doing = useStore(chat, (s) => s.turns.at(-1)?.tools.findLast((t) => t.status === 'running')?.label)
  return (
    <span className={running ? 'statusbar-agent busy' : 'statusbar-agent'}>
      <span className="dot" /> {running ? `Agent: ${doing ?? 'working'}` : 'Agent idle'}
    </span>
  )
}

export function StatusBar() {
  const info = useAppInfo()
  const agentsOn = useStore(mcp, (s) => s.state?.listening ?? false)
  return (
    <footer className="statusbar">
      <AgentState />
      <Account />
      <button type="button" className="statusbar-agents" onClick={() => runCommand('agents.connect')}>
        {agentsOn ? '● Agents on' : 'Agents'}
      </button>
      <span className="statusbar-right">{info ? `${info.name} ${info.version} · Electron ${info.electron}` : ''}</span>
    </footer>
  )
}
