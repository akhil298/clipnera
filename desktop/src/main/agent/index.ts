import { join } from 'node:path'
import { app, BrowserWindow, ipcMain, safeStorage } from 'electron'
import type { AgentRequest } from '../../shared/agent'
import { IPC, type AgentMessage } from '../../shared/ipc'
import type { Account } from '../auth'
import type { ExportService } from '../export/service'
import type { ProjectService } from '../project/service'
import type { McpAccess } from '../mcp'
import { ClaudeChat } from './claudeChat'
import { AnthropicKeyStore } from './keyStore'
import { AgentService } from './service'

const id = (value: unknown, name: string): string => {
  if (typeof value !== 'string' || !value) throw new Error(`${name} is required`)
  return value
}

export function setUpAgent(account: Account, projects: ProjectService, exports: ExportService, access: McpAccess): AgentService {
  const emit = (message: AgentMessage) => BrowserWindow.getAllWindows().forEach((w) => w.webContents.send(IPC.agentEvent, message))
  // The chat on the person's own Claude: their Claude Code, with only the editor's tools.
  const chat = new ClaudeChat({
    claudePath: () => access.claude.find(),
    editorAccess: () => access.ensureOn(),
    workdir: join(app.getPath('userData'), 'claude'),
    emit: (event) => emit({ source: 'agent', message: event })
  })
  const offered = async () => (await access.claudeChatOn()) && Boolean((await access.claude.status()).signedIn)
  const keys = new AnthropicKeyStore(join(app.getPath('userData'), 'anthropic-key.bin'), safeStorage)
  const agent = new AgentService({
    token: account.token,
    settled: () => void account.refresh().catch(() => undefined),
    rendering: (render) => void exports.follow(render),
    projects,
    emit,
    claude: { chat, offered },
    anthropicKey: () => keys.get()
  })
  ipcMain.handle(IPC.claudeKey, () => keys.describe())
  ipcMain.handle(IPC.claudeSetKey, async (_event, key: unknown) => {
    await keys.set(String(key))
    return keys.describe()
  })
  ipcMain.handle(IPC.claudeClearKey, async () => {
    await keys.clear()
    return keys.describe()
  })
  ipcMain.handle(IPC.agentModels, () => agent.models())
  // The backend validates the request; this only checks it is an object with a prompt.
  ipcMain.handle(IPC.agentSend, (_event, request: AgentRequest) => {
    if (!request || typeof request.prompt !== 'string') throw new Error('prompt is required')
    return agent.send(request)
  })
  ipcMain.handle(IPC.agentStop, () => agent.stop())
  ipcMain.handle(IPC.agentApprove, (_event, planId: unknown) => agent.approve(id(planId, 'planId')))
  ipcMain.handle(IPC.agentReject, (_event, planId: unknown) => agent.reject(id(planId, 'planId')))
  ipcMain.handle(IPC.agentVoice, (_event, audio: unknown, type: unknown, seconds: unknown) => {
    if (!(audio instanceof Uint8Array) || typeof type !== 'string' || typeof seconds !== 'number') throw new Error('Not a voice note')
    return agent.transcribe(audio, type, seconds)
  })
  ipcMain.handle(IPC.agentUndoStep, (_event, stepId: unknown) => agent.undoStep(id(stepId, 'stepId')))
  return agent
}
