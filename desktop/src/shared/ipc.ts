/** Channel names and payloads shared by the main process, the preload script and the renderer. */

import type { LibraryGraphic, LibrarySound, StylePreference, UserProfileResponse } from './api'
import type { TimelineOp } from '@timeline'
import type { AgentEvent, AgentRequest, AiModels, PlanCard, PlanEvent } from './agent'
import type { ExportState } from './export'
import type { MediaItem } from './media'
import type { ProjectSnapshot, ProjectState } from './project'
import type { Take } from './takes'

export const IPC = {
  appInfo: 'app:info',
  runCommand: 'command:run',
  authGet: 'auth:get',
  authSignIn: 'auth:signIn',
  authCancel: 'auth:cancel',
  authSignOut: 'auth:signOut',
  authChanged: 'auth:changed',
  mediaList: 'media:list',
  mediaImport: 'media:import',
  mediaPick: 'media:pick',
  mediaRemove: 'media:remove',
  mediaChanged: 'media:changed',
  projectGet: 'project:get',
  projectApply: 'project:apply',
  projectUndo: 'project:undo',
  projectRedo: 'project:redo',
  projectRefresh: 'project:refresh',
  projectRetryAnalysis: 'project:retryAnalysis',
  projectSounds: 'project:sounds',
  projectGraphics: 'project:graphics',
  projectRules: 'project:rules',
  projectSetRules: 'project:setRules',
  projectStyle: 'project:style',
  projectForgetStyle: 'project:forgetStyle',
  projectTakes: 'project:takes',
  projectSaveTake: 'project:saveTake',
  projectRemoveTake: 'project:removeTake',
  projectChanged: 'project:changed',
  agentModels: 'agent:models',
  agentSend: 'agent:send',
  agentStop: 'agent:stop',
  agentApprove: 'agent:approve',
  agentReject: 'agent:reject',
  agentUndoStep: 'agent:undoStep',
  agentVoice: 'agent:voice',
  agentEvent: 'agent:event',
  exportGet: 'export:get',
  exportStart: 'export:start',
  exportReveal: 'export:reveal',
  exportChanged: 'export:changed',
  mcpGet: 'mcp:get',
  mcpSetEnabled: 'mcp:setEnabled',
  mcpChanged: 'mcp:changed',
  mcpRequest: 'mcp:request',
  mcpRespond: 'mcp:respond'
} as const

export interface AppInfo {
  name: string
  version: string
  electron: string
  platform: string
  /** The Clipnera website, for Terms and Privacy links. */
  webUrl: string
  /** The backend, for files it serves (sound effects). */
  apiUrl: string
}

export type AuthState =
  | { status: 'loading' }
  | { status: 'signedOut'; error?: string }
  | { status: 'waiting' }
  | { status: 'signedIn'; user: UserProfileResponse }

export interface AuthBridge {
  get(): Promise<AuthState>
  /** Opens Google in the browser; the new state arrives through onChange. */
  signIn(acceptTerms: boolean): Promise<void>
  cancel(): Promise<void>
  signOut(): Promise<void>
  onChange(listener: (state: AuthState) => void): () => void
}

export interface MediaBridge {
  list(): Promise<MediaItem[]>
  /** Adds files by absolute path; returns the items that were new. */
  import(paths: string[]): Promise<MediaItem[]>
  /** Shows the Import Media dialog; returns the items that were added. */
  pick(): Promise<MediaItem[]>
  remove(id: string): Promise<void>
  onChange(listener: (items: MediaItem[]) => void): () => void
  /** The path of a file dropped on the window. */
  pathForFile(file: File): string
}

export interface ProjectBridge {
  get(): Promise<ProjectState>
  /** Sends edits to the project; resolves with the project as the backend has it after them. */
  apply(ops: TimelineOp[]): Promise<ProjectSnapshot>
  undo(): Promise<ProjectSnapshot>
  redo(): Promise<ProjectSnapshot>
  refresh(): Promise<ProjectSnapshot>
  /** Asks the AI to look at a file again after it failed. */
  retryAnalysis(assetId: string): Promise<void>
  /** Searches the sound effects library. */
  sounds(query: string): Promise<LibrarySound[]>
  /** The animated graphics shelf, with playable URLs. */
  graphics(): Promise<LibraryGraphic[]>
  /** The open project's Edit Rules, and replacing them. */
  rules(): Promise<string[]>
  setRules(rules: string[]): Promise<string[]>
  /** What the AI learned from the user's corrections, and forgetting one. */
  style(): Promise<StylePreference[]>
  forgetStyle(key: string): Promise<StylePreference[]>
  /** Saved versions of the edit, newest first; saving one keeps the project as it is now. */
  takes(): Promise<Take[]>
  saveTake(name: string, source: Take['source']): Promise<Take[]>
  removeTake(id: string): Promise<Take[]>
  onChange(listener: (state: ProjectState) => void): () => void
}

/** What the chat receives: the agent's events, a running plan's events, and the app's own. */
export type AgentMessage =
  | { source: 'agent'; message: AgentEvent }
  | { source: 'plan'; planId: string; message: PlanEvent }
  | { source: 'app'; message: { event: 'stopped' } | { event: 'idle' } | { event: 'error'; data: { message: string } } }

export interface AgentBridge {
  models(): Promise<AiModels>
  /** Resolves when the turn is over; its events arrive through onEvent meanwhile. */
  send(request: AgentRequest): Promise<void>
  stop(): Promise<void>
  approve(planId: string): Promise<PlanCard>
  reject(planId: string): Promise<PlanCard>
  undoStep(stepId: string): Promise<void>
  /** What was said in a voice note (at most a minute). */
  transcribe(audio: Uint8Array, type: string, seconds: number): Promise<string>
  onEvent(listener: (message: AgentMessage) => void): () => void
}

export interface ExportBridge {
  get(): Promise<ExportState>
  /** Renders the saved project on the backend and saves the MP4; progress arrives through onChange. */
  start(): Promise<void>
  /** Shows the last finished video in Finder. */
  reveal(): Promise<void>
  onChange(listener: (state: ExportState) => void): () => void
}

/** Whether VS Code and terminal agents (Claude Code, Codex) can drive the editor, and how to connect them. */
export interface McpState {
  enabled: boolean
  listening: boolean
  port: number
  token: string
  url: string
  /** The stdio bridge for agents that start a command (Codex, or Claude Code without HTTP). */
  bridge: string
  error: string | null
}

/** What an outside agent asks the editor window to do; it answers with mcp.respond. */
export type McpWindowRequest =
  | { id: string; kind: 'commands' }
  | { id: string; kind: 'run'; command: string; args: unknown; client: string }
  | { id: string; kind: 'ask'; prompt: string; client: string }

export type McpWindowResponse = { ok: true; result: unknown } | { ok: false; error: string }

export interface McpBridge {
  get(): Promise<McpState>
  setEnabled(enabled: boolean): Promise<McpState>
  onChange(listener: (state: McpState) => void): () => void
  onRequest(listener: (request: McpWindowRequest) => void): () => void
  respond(id: string, response: McpWindowResponse): Promise<void>
}

export interface ClipneraBridge {
  appInfo(): Promise<AppInfo>
  /** Called when a native menu item asks the workbench to run a command. Returns an unsubscribe function. */
  onRunCommand(listener: (commandId: string) => void): () => void
  auth: AuthBridge
  media: MediaBridge
  project: ProjectBridge
  agent: AgentBridge
  export: ExportBridge
  mcp: McpBridge
}
