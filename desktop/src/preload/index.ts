import { contextBridge, ipcRenderer, webUtils, type IpcRendererEvent } from 'electron'
import { IPC, type AgentMessage, type AuthState, type ClipneraBridge, type McpState, type McpWindowRequest } from '../shared/ipc'
import type { ExportState } from '../shared/export'
import type { MediaItem } from '../shared/media'
import type { ProjectState } from '../shared/project'

function subscribe<T>(channel: string, listener: (payload: T) => void): () => void {
  const handler = (_event: IpcRendererEvent, payload: T) => listener(payload)
  ipcRenderer.on(channel, handler)
  return () => ipcRenderer.off(channel, handler)
}

const bridge: ClipneraBridge = {
  appInfo: () => ipcRenderer.invoke(IPC.appInfo),
  onRunCommand: (listener) => subscribe<string>(IPC.runCommand, listener),
  auth: {
    get: () => ipcRenderer.invoke(IPC.authGet),
    signIn: (acceptTerms) => ipcRenderer.invoke(IPC.authSignIn, acceptTerms === true),
    cancel: () => ipcRenderer.invoke(IPC.authCancel),
    signOut: () => ipcRenderer.invoke(IPC.authSignOut),
    onChange: (listener) => subscribe<AuthState>(IPC.authChanged, listener)
  },
  media: {
    list: () => ipcRenderer.invoke(IPC.mediaList),
    import: (paths) => ipcRenderer.invoke(IPC.mediaImport, paths),
    pick: () => ipcRenderer.invoke(IPC.mediaPick),
    remove: (id) => ipcRenderer.invoke(IPC.mediaRemove, id),
    onChange: (listener) => subscribe<MediaItem[]>(IPC.mediaChanged, listener),
    pathForFile: (file) => webUtils.getPathForFile(file)
  },
  project: {
    get: () => ipcRenderer.invoke(IPC.projectGet),
    apply: (ops) => ipcRenderer.invoke(IPC.projectApply, ops),
    undo: () => ipcRenderer.invoke(IPC.projectUndo),
    redo: () => ipcRenderer.invoke(IPC.projectRedo),
    refresh: () => ipcRenderer.invoke(IPC.projectRefresh),
    retryAnalysis: (assetId) => ipcRenderer.invoke(IPC.projectRetryAnalysis, assetId),
    sounds: (query) => ipcRenderer.invoke(IPC.projectSounds, query),
    graphics: () => ipcRenderer.invoke(IPC.projectGraphics),
    rules: () => ipcRenderer.invoke(IPC.projectRules),
    setRules: (rules) => ipcRenderer.invoke(IPC.projectSetRules, rules),
    style: () => ipcRenderer.invoke(IPC.projectStyle),
    forgetStyle: (key) => ipcRenderer.invoke(IPC.projectForgetStyle, key),
    takes: () => ipcRenderer.invoke(IPC.projectTakes),
    saveTake: (name, source) => ipcRenderer.invoke(IPC.projectSaveTake, name, source),
    removeTake: (id) => ipcRenderer.invoke(IPC.projectRemoveTake, id),
    onChange: (listener) => subscribe<ProjectState>(IPC.projectChanged, listener)
  },
  agent: {
    models: () => ipcRenderer.invoke(IPC.agentModels),
    send: (request) => ipcRenderer.invoke(IPC.agentSend, request),
    stop: () => ipcRenderer.invoke(IPC.agentStop),
    approve: (planId) => ipcRenderer.invoke(IPC.agentApprove, planId),
    reject: (planId) => ipcRenderer.invoke(IPC.agentReject, planId),
    undoStep: (stepId) => ipcRenderer.invoke(IPC.agentUndoStep, stepId),
    transcribe: (audio, type, seconds) => ipcRenderer.invoke(IPC.agentVoice, audio, type, seconds),
    onEvent: (listener) => subscribe<AgentMessage>(IPC.agentEvent, listener)
  },
  export: {
    get: () => ipcRenderer.invoke(IPC.exportGet),
    start: () => ipcRenderer.invoke(IPC.exportStart),
    reveal: () => ipcRenderer.invoke(IPC.exportReveal),
    onChange: (listener) => subscribe<ExportState>(IPC.exportChanged, listener)
  },
  mcp: {
    get: () => ipcRenderer.invoke(IPC.mcpGet),
    setEnabled: (enabled) => ipcRenderer.invoke(IPC.mcpSetEnabled, enabled === true),
    onChange: (listener) => subscribe<McpState>(IPC.mcpChanged, listener),
    onRequest: (listener) => subscribe<McpWindowRequest>(IPC.mcpRequest, listener),
    respond: (id, response) => ipcRenderer.invoke(IPC.mcpRespond, id, response)
  }
}

contextBridge.exposeInMainWorld('clipnera', bridge)
