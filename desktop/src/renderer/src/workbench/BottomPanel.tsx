import { commands, runCommand } from '../commands'
import { BOTTOM_TABS, layout, type BottomTab } from '../state/layout'
import { problems } from '../state/problems'
import { useStore } from '../state/store'
import type { Problem } from '../timeline/problems'

const TAB_LABELS: Record<BottomTab, string> = { activity: 'Activity', problems: 'Problems' }

function time(at: number): string {
  return new Date(at).toLocaleTimeString([], { hour12: false })
}

function Activity() {
  const entries = useStore(commands.activity, (s) => s.entries)
  if (entries.length === 0) return <p className="empty">Every command you or the AI run shows up here.</p>
  return (
    <ol className="activity" aria-label="Activity log">
      {[...entries].reverse().map((e) => (
        <li key={e.seq} className={e.ok ? '' : 'failed'}>
          <span className="muted">{time(e.at)}</span>
          <span className={`actor actor-${e.actor}`} title={e.by}>{e.actor === 'ai' ? 'AI' : e.actor === 'external' ? (e.by ?? 'Agent') : 'You'}</span>
          <code>{e.commandId}</code>
          <span>{e.ok ? e.title : `${e.title} failed: ${e.error}`}</span>
        </li>
      ))}
    </ol>
  )
}

function goTo(problem: Problem) {
  runCommand('player.showTimeline')
  if (problem.at !== undefined) runCommand('player.seek', { seconds: problem.at })
  if (problem.item) runCommand('timeline.select', { items: [problem.item] })
}

/** Asks the AI to fix it, about the few seconds around it. */
function askAi(problem: Problem) {
  if (problem.at !== undefined) runCommand('timeline.setRange', { from: Math.max(0, problem.at - 1), to: problem.at + 3 })
  runCommand('agent.send', { prompt: `Fix this: ${problem.title}` })
}

function Problems() {
  const list = useStore(problems, (s) => s.list)
  if (list.length === 0) return <p className="empty">No problems found. The export will look like the timeline.</p>
  return (
    <ul className="problems" aria-label="Problems list">
      {list.map((p) => (
        <li key={p.id} className={`problem-${p.severity}`}>
          <span className="problem-mark" aria-label={p.severity === 'warning' ? 'Warning' : 'Note'}>{p.severity === 'warning' ? '▲' : 'ⓘ'}</span>
          <span className="problem-title">{p.title}</span>
          {(p.at !== undefined || p.item) && <button type="button" onClick={() => goTo(p)}>Go to</button>}
          {p.fix && <button type="button" className="problem-fix" onClick={() => runCommand(p.fix!.command, p.fix!.args)}>{p.fix.label}</button>}
          <button type="button" onClick={() => askAi(p)}>Ask AI</button>
        </li>
      ))}
    </ul>
  )
}

export function BottomPanel() {
  const tab = useStore(layout, (s) => s.bottomTab)
  const count = useStore(problems, (s) => s.list.length)
  return (
    <section className="bottompanel" aria-label="Bottom panel">
      <div className="tabs" role="tablist">
        {BOTTOM_TABS.map((t) => (
          <button key={t} type="button" role="tab" aria-selected={t === tab} onClick={() => runCommand('view.showBottomTab', { tab: t })}>
            {TAB_LABELS[t]}
            {t === 'problems' && count > 0 && <span className="tab-count">{count}</span>}
          </button>
        ))}
      </div>
      <div className="tab-body" role="tabpanel">
        {tab === 'activity' ? <Activity /> : <Problems />}
      </div>
    </section>
  )
}
