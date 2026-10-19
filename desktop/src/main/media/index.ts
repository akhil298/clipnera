import { existsSync } from 'node:fs'
import { isAbsolute, join } from 'node:path'
import { app, BrowserWindow, dialog, ipcMain, protocol } from 'electron'
import { IPC } from '../../shared/ipc'
import { MEDIA_SCHEME } from '../../shared/media'
import { EngineClient } from '../engine/client'
import { MediaLibrary } from './library'
import { serveFile } from './serveFile'
import { SHELF_HOST, ShelfCache } from './shelfCache'

/** Call before the app is ready: lets the renderer load thumbnails and play media from the library. */
export function registerMediaScheme(): void {
  protocol.registerSchemesAsPrivileged([{ scheme: MEDIA_SCHEME, privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true, corsEnabled: true } }])
}

/** clipnera-engine next to the app when packaged, or the local build in development. */
function engineBinary(): string {
  if (process.env.CLIPNERA_ENGINE_PATH) return process.env.CLIPNERA_ENGINE_PATH
  return app.isPackaged ? join(process.resourcesPath, 'clipnera-engine') : join(app.getAppPath(), 'engine/.build/release/clipnera-engine')
}

const MEDIA_EXTENSIONS = ['mp4', 'mov', 'm4v', 'mkv', 'webm', 'avi', 'mxf', 'mp3', 'm4a', 'wav', 'aif', 'aiff', 'aac', 'flac', 'caf']

function paths(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((p): p is string => typeof p === 'string' && isAbsolute(p)) : []
}

export function setUpMedia(): { engine: EngineClient; library: MediaLibrary; shelf: ShelfCache } {
  const binary = engineBinary()
  const engine = new EngineClient(binary)
  const library = new MediaLibrary(engine, join(app.getPath('userData'), 'media-cache'), (items) =>
    BrowserWindow.getAllWindows().forEach((w) => w.webContents.send(IPC.mediaChanged, items))
  )
  if (!existsSync(binary)) console.error(`clipnera-engine not found at ${binary}. Run: npm run engine:build`)
  const shelf = new ShelfCache(join(app.getPath('userData'), 'shelf-cache'))

  protocol.handle(MEDIA_SCHEME, (request) => {
    const url = new URL(request.url)
    const file = url.hostname === SHELF_HOST ? shelf.filePath(url.pathname.slice(1)) : library.filePath(url.hostname, url.pathname.slice(1))
    return file ? serveFile(file, request) : new Response('Not found', { status: 404 })
  })

  ipcMain.handle(IPC.mediaList, () => library.list())
  ipcMain.handle(IPC.mediaImport, (_event, value: unknown) => library.import(paths(value)))
  ipcMain.handle(IPC.mediaRemove, (_event, id: unknown) => (typeof id === 'string' ? library.remove(id) : undefined))
  ipcMain.handle(IPC.mediaPick, async (event) => {
    const window = BrowserWindow.fromWebContents(event.sender)
    const options = {
      title: 'Import Media',
      properties: ['openFile', 'multiSelections'] as Array<'openFile' | 'multiSelections'>,
      filters: [{ name: 'Video and audio', extensions: MEDIA_EXTENSIONS }]
    }
    const picked = window ? await dialog.showOpenDialog(window, options) : await dialog.showOpenDialog(options)
    return picked.canceled ? [] : library.import(picked.filePaths)
  })

  return { engine, library, shelf }
}
