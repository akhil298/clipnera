import { join } from 'node:path'
import { app, BrowserWindow, ipcMain, Menu, session, shell } from 'electron'
import { IPC, type AppInfo } from '../shared/ipc'
import { API_URL } from './api'
import { setUpAuth } from './auth'
import { setUpMedia, registerMediaScheme } from './media'
import { setUpProject } from './project'
import { setUpAgent } from './agent'
import { setUpExport } from './export'
import { setUpMcp } from './mcp'
import { buildMenu } from './menu'

// Tests run against a throwaway profile so they never touch the real session.
if (process.env.CLIPNERA_USER_DATA) app.setPath('userData', process.env.CLIPNERA_USER_DATA)
registerMediaScheme()
// End-to-end tests use Chromium's fake microphone instead of the Mac's.
if (!app.isPackaged && process.env.CLIPNERA_E2E === '1') {
  app.commandLine.appendSwitch('use-fake-device-for-media-stream')
  app.commandLine.appendSwitch('use-fake-ui-for-media-stream')
}

function createWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 680,
    show: false,
    title: 'Clipnera Studio',
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 14, y: 13 },
    backgroundColor: '#141210',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false
    }
  })

  window.once('ready-to-show', () => window.show())

  // The workbench is a single page: links open in the browser and the window never navigates away.
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://')) void shell.openExternal(url)
    return { action: 'deny' }
  })
  window.webContents.on('will-navigate', (event) => event.preventDefault())

  const devUrl = process.env.ELECTRON_RENDERER_URL
  if (devUrl) void window.loadURL(devUrl)
  else void window.loadFile(join(__dirname, '../renderer/index.html'))

  return window
}

function appInfo(): AppInfo {
  return {
    name: app.getName(),
    version: app.getVersion(),
    electron: process.versions.electron,
    platform: process.platform,
    webUrl: (process.env.CLIPNERA_WEB_URL ?? 'https://clipnera.com').replace(/\/$/, ''),
    apiUrl: API_URL
  }
}

void app.whenReady().then(async () => {
  ipcMain.handle(IPC.appInfo, appInfo)
  // The window may ask for the microphone (voice notes) and nothing else.
  session.defaultSession.setPermissionRequestHandler((_wc, permission, allow, details) => {
    const media = details as { mediaTypes?: string[] }
    allow(permission === 'media' && (media.mediaTypes ?? []).every((t) => t === 'audio'))
  })
  const account = await setUpAuth()
  const { engine, library, shelf } = setUpMedia()
  const projects = setUpProject(account, library, shelf)
  setUpAgent(account, projects, setUpExport(account, projects))
  setUpMcp(projects, library)
  app.on('will-quit', () => engine.dispose())
  Menu.setApplicationMenu(
    buildMenu((commandId) => {
      const window = BrowserWindow.getFocusedWindow() ?? BrowserWindow.getAllWindows()[0]
      window?.webContents.send(IPC.runCommand, commandId)
    })
  )
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
