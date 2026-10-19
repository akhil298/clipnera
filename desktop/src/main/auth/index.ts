import { join } from 'node:path'
import { app, BrowserWindow, ipcMain, safeStorage, shell } from 'electron'
import type { UserProfileResponse } from '../../shared/api'
import { IPC, type AuthState } from '../../shared/ipc'
import { api } from '../api'
import { AuthSession } from './session'
import { TokenStore } from './tokenStore'

/**
 * End-to-end tests set CLIPNERA_E2E so "the browser" is a plain request that follows redirects
 * (fake Google → callback → the app's loopback port) instead of opening a real browser tab.
 */
async function openBrowser(url: string): Promise<void> {
  if (process.env.CLIPNERA_E2E === '1') {
    await fetch(url)
    return
  }
  await shell.openExternal(url)
}

/** Stand-in account for `npm run dev:preview`, which shows the editor without a backend. */
const PREVIEW: AuthState = {
  status: 'signedIn',
  user: {
    id: 'preview',
    name: 'Preview (not signed in)',
    email: '',
    avatar_url: null,
    avatar_initials: 'P',
    plan: 'preview',
    plan_expires_at: null,
    ai_credits_minutes_remaining: 0,
    ai_credits_total: 0,
    features: {},
    daily_limits: {},
    usage_today: {},
    active_workspace_id: null,
    providers: [],
    role: 'user',
    email_notifications: false,
    onboarding_completed: true
  } satisfies UserProfileResponse
}

/** The signed-in account, as the rest of the main process sees it. */
export interface Account {
  /** Preview mode: no backend, projects live on this Mac. */
  preview: boolean
  state(): AuthState
  token(): Promise<string | null>
  /** Re-reads the profile (plan, credits), e.g. after the AI spent credits. */
  refresh(): Promise<void>
  subscribe(listener: (state: AuthState) => void): () => void
}

function broadcaster() {
  const listeners = new Set<(state: AuthState) => void>()
  return {
    notify(state: AuthState) {
      BrowserWindow.getAllWindows().forEach((w) => w.webContents.send(IPC.authChanged, state))
      listeners.forEach((listener) => listener(state))
    },
    subscribe(listener: (state: AuthState) => void) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    }
  }
}

function setUpPreview(): Account {
  ipcMain.handle(IPC.authGet, () => PREVIEW)
  for (const channel of [IPC.authSignIn, IPC.authCancel, IPC.authSignOut]) ipcMain.handle(channel, () => undefined)
  return { preview: true, state: () => PREVIEW, token: async () => null, refresh: async () => undefined, subscribe: () => () => undefined }
}

export async function setUpAuth(): Promise<Account> {
  // Development only: a packaged app always signs in for real.
  if (!app.isPackaged && process.env.CLIPNERA_PREVIEW === '1') return setUpPreview()

  const store = new TokenStore(join(app.getPath('userData'), 'session.bin'), {
    encrypt: (text) => safeStorage.encryptString(text),
    decrypt: (data) => safeStorage.decryptString(data)
  })
  // Development only: start signed in with a token minted for a local backend (real end-to-end tests).
  if (!app.isPackaged && process.env.CLIPNERA_DEV_TOKEN) {
    await store.save({ accessToken: process.env.CLIPNERA_DEV_TOKEN, expiresAt: Date.now() + 24 * 3600_000 })
  }
  const changes = broadcaster()
  const session = new AuthSession({ api, store, openBrowser, onChange: changes.notify })

  ipcMain.handle(IPC.authGet, () => session.get())
  ipcMain.handle(IPC.authSignIn, (_event, acceptTerms: unknown) => session.signIn(acceptTerms === true))
  ipcMain.handle(IPC.authCancel, () => session.cancel())
  ipcMain.handle(IPC.authSignOut, () => session.signOut())

  void session.restore()
  return { preview: false, state: () => session.get(), token: () => session.token(), refresh: () => session.restore(), subscribe: changes.subscribe }
}
