import { BrowserWindow, ipcMain } from 'electron'
import type { AgentRequest } from '../../shared/agent'
import { IPC } from '../../shared/ipc'
import type { Account } from '../auth'
import type { ExportService } from '../export/service'
import type { ProjectService } from '../project/service'
import { AgentService } from './service'

const id = (value: unknown, name: string): string => {
  if (typeof value !== 'string' || !value) throw new Error(`${name} is required`)
  return value
}

export function setUpAgent(account: Account, projects: ProjectService, exports: ExportService): AgentService {
  const agent = new AgentService({
    token: account.token,
    settled: () => void account.refresh().catch(() => undefined),
    rendering: (render) => void exports.follow(render),
    projects,
    emit: (message) => BrowserWindow.getAllWindows().forEach((w) => w.webContents.send(IPC.agentEvent, message))
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
