import { useEffect } from 'react'
import { commands } from './commands'
import { registerAccountCommands } from './commands/account'
import { registerAgentCommands } from './commands/agent'
import { registerCaptionCommands } from './commands/captions'
import { registerLibraryCommands } from './commands/library'
import { registerSoundCommands } from './commands/sounds'
import { registerEffectCommands } from './commands/effects'
import { registerRuleCommands } from './commands/rules'
import { registerTakeCommands } from './commands/takes'
import { connectExternalAgents } from './commands/external'
import { registerExportCommands } from './commands/export'
import { registerMediaCommands } from './commands/media'
import { registerPlayerCommands } from './commands/player'
import { registerTimelineCommands } from './commands/timeline'
import { useFileDrop } from './commands/useFileDrop'
import { useCommandInputs } from './commands/useCommandInputs'
import { registerViewCommands } from './commands/view'
import { auth, connectAuth } from './state/auth'
import { layout } from './state/layout'
import { connectExport } from './state/export'
import { connectMedia, media } from './state/media'
import { connectProblems } from './state/problems'
import { connectRules } from './state/rules'
import { connectTakes } from './state/takes'
import { connectMcp, mcp } from './state/mcp'
import { player } from './player/player'
import { assetUrl, connectProject, project } from './state/project'
import { useStore } from './state/store'
import { ActivityBar } from './workbench/ActivityBar'
import { AiPanel } from './workbench/AiPanel'
import { BottomPanel } from './workbench/BottomPanel'
import { AgentsSheet } from './workbench/AgentsSheet'
import { CommandPalette } from './workbench/CommandPalette'
import { SidePanel } from './workbench/SidePanel'
import { SignIn } from './workbench/SignIn'
import { StatusBar } from './workbench/StatusBar'
import { Timeline } from './workbench/Timeline'
import { TitleBar } from './workbench/TitleBar'
import { Viewer } from './workbench/Viewer'

export function App() {
  useEffect(() => registerViewCommands(commands, layout), [])
  useEffect(() => registerAccountCommands(commands), [])
  useEffect(() => registerMediaCommands(commands, layout), [])
  useEffect(() => registerPlayerCommands(commands, player, media), [])
  useEffect(() => registerTimelineCommands(commands, player), [])
  useEffect(() => registerCaptionCommands(commands, player), [])
  useEffect(() => registerSoundCommands(commands, player), [])
  useEffect(() => registerLibraryCommands(commands, player), [])
  useEffect(() => registerEffectCommands(commands, player), [])
  useEffect(() => registerRuleCommands(commands), [])
  useEffect(() => registerTakeCommands(commands), [])
  useEffect(connectTakes, [])
  useEffect(connectMcp, [])
  useEffect(() => connectExternalAgents(commands, player), [])
  useEffect(
    () =>
      commands.register({
        id: 'agents.connect',
        title: 'Connect Claude Code or Codex…',
        category: 'AI',
        description: 'Let agents on this Mac (Claude Code, Codex) use Clipnera Studio.',
        aiCanRun: false,
        run: () => mcp.set({ open: true })
      }),
    []
  )
  useEffect(
    () =>
      commands.register({
        id: 'agents.useClaude',
        title: 'Use My Claude…',
        category: 'AI',
        description: 'Edit with your own Claude (Pro or Max) through Claude Code, connected to this editor.',
        aiCanRun: false,
        run: () => mcp.set({ open: true })
      }),
    []
  )
  useEffect(connectRules, [])
  useEffect(connectProblems, [])
  useEffect(() => registerAgentCommands(commands, player), [])
  useEffect(() => registerExportCommands(commands), [])
  useEffect(connectExport, [])
  useEffect(() => void window.clipnera.appInfo().then((info) => player.setApiUrl(info.apiUrl)), [])
  useEffect(connectProject, [])
  // The viewer follows the project, and the media list (local copies play before the cloud ones).
  useEffect(() => {
    const show = () => player.setTimeline(project.get().timeline, assetUrl)
    const offProject = project.subscribe(show)
    const offMedia = media.subscribe(show)
    return () => {
      offProject()
      offMedia()
    }
  }, [])
  useEffect(connectAuth, [])
  useEffect(connectMedia, [])
  useFileDrop()
  useCommandInputs()
  const { sideVisible, bottomVisible, aiVisible } = useStore(layout, (s) => s)
  const status = useStore(auth, (s) => s.state.status)

  if (status === 'loading') return <div className="splash" />
  if (status !== 'signedIn') return <SignIn />

  return (
    <div className="workbench">
      <TitleBar />
      <div className="workbench-body">
        <ActivityBar />
        {sideVisible && <SidePanel />}
        <main className="center">
          <Viewer />
          <Timeline />
          {bottomVisible && <BottomPanel />}
        </main>
        {aiVisible && <AiPanel />}
      </div>
      <StatusBar />
      <CommandPalette />
      <AgentsSheet />
    </div>
  )
}
