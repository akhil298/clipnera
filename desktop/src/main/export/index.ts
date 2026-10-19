import { join } from 'node:path'
import { app, BrowserWindow, ipcMain, shell } from 'electron'
import { IPC } from '../../shared/ipc'
import type { Account } from '../auth'
import type { ProjectService } from '../project/service'
import { ExportService } from './service'

export function setUpExport(account: Account, projects: ProjectService): ExportService {
  const exports = new ExportService({
    token: account.token,
    project: () => projects.get().project,
    // Tests send finished videos somewhere throwaway.
    folder: process.env.CLIPNERA_EXPORT_DIR ?? join(app.getPath('videos'), 'Clipnera'),
    onChange: (state) => BrowserWindow.getAllWindows().forEach((w) => w.webContents.send(IPC.exportChanged, state))
  })
  ipcMain.handle(IPC.exportGet, () => exports.get())
  ipcMain.handle(IPC.exportStart, () => exports.start())
  ipcMain.handle(IPC.exportReveal, () => {
    const file = exports.get().file
    if (file) shell.showItemInFolder(file)
  })
  return exports
}
