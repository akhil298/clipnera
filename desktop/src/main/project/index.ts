import { join } from 'node:path'
import type { TimelineOp } from '@timeline'
import { app, BrowserWindow, ipcMain } from 'electron'
import { IPC, type AuthState } from '../../shared/ipc'
import type { Account } from '../auth'
import type { MediaLibrary, MediaProject } from '../media/library'
import { RemoteProjectBackend } from './backend'
import type { ShelfCache } from '../media/shelfCache'
import { LocalProjectBackend } from './localBackend'
import { RulesStore } from './rules'
import { ProjectService } from './service'
import { TakesStore } from './takes'

const usesAsset = (service: ProjectService, assetId: string) =>
  service.get().project?.timeline.tracks.some((t) => t.items.some((i) => i.type === 'clip' && i.asset === assetId)) ?? false

/** Opens the account's project when it signs in, and connects the media library to it. */
export function setUpProject(account: Account, library: MediaLibrary, shelf: ShelfCache): ProjectService {
  const service = new ProjectService()
  const userData = app.getPath('userData')
  service.subscribe((state) => BrowserWindow.getAllWindows().forEach((w) => w.webContents.send(IPC.projectChanged, state)))

  const media: MediaProject = {
    fps: () => service.get().project?.timeline.fps ?? 30,
    upload: (file, onProgress) => service.upload(file, onProgress),
    addAsset: async (asset) => void (await service.apply([{ op: 'add_asset', asset }])),
    hasAsset: (id) => Boolean(service.get().project?.timeline.assets[id]),
    usesAsset: (id) => usesAsset(service, id)
  }

  let openFor: string | null = null
  const follow = async (state: AuthState) => {
    if (state.status !== 'signedIn') {
      if (state.status === 'signedOut' && openFor) {
        openFor = null
        library.close()
        service.close()
      }
      return
    }
    if (openFor === state.user.id) return
    openFor = state.user.id
    const backend = account.preview ? new LocalProjectBackend(join(userData, 'preview', 'project.json')) : new RemoteProjectBackend(account.token)
    const project = await service.open(backend)
    if (project && openFor === state.user.id) await library.open(media, join(userData, 'projects', project.id, 'media.json'))
  }
  account.subscribe((state) => void follow(state))
  void follow(account.state())

  ipcMain.handle(IPC.projectGet, () => service.get())
  ipcMain.handle(IPC.projectApply, (_event, ops: unknown) => {
    if (!Array.isArray(ops) || ops.length === 0) throw new Error('ops must be a non-empty list')
    return service.apply(ops as TimelineOp[])
  })
  ipcMain.handle(IPC.projectUndo, () => service.undo())
  ipcMain.handle(IPC.projectRedo, () => service.redo())
  ipcMain.handle(IPC.projectRefresh, () => service.refresh())
  const rules = () => {
    const id = service.get().project?.id
    if (!id) throw new Error('No project is open')
    return new RulesStore(join(userData, 'projects', id, 'rules.json'))
  }
  const takes = () => {
    const id = service.get().project?.id
    if (!id) throw new Error('No project is open')
    return new TakesStore(join(userData, 'projects', id, 'takes.json'))
  }
  ipcMain.handle(IPC.projectTakes, () => takes().list())
  // A take is the project as the backend has it now, so it never holds an edit that didn't land.
  ipcMain.handle(IPC.projectSaveTake, (_event, name: unknown, source: unknown) => {
    const timeline = service.get().project?.timeline
    if (!timeline) throw new Error('No project is open')
    return takes().save(typeof name === 'string' ? name : '', timeline, source === 'auto' ? 'auto' : 'manual')
  })
  ipcMain.handle(IPC.projectRemoveTake, (_event, id: unknown) => takes().remove(String(id)))
  ipcMain.handle(IPC.projectRules, () => rules().get())
  ipcMain.handle(IPC.projectSetRules, (_event, list: unknown) => rules().set(list))
  ipcMain.handle(IPC.projectStyle, () => service.style())
  ipcMain.handle(IPC.projectForgetStyle, (_event, key: unknown) => {
    if (typeof key !== 'string' || !key) throw new Error('key is required')
    return service.forgetStyle(key)
  })
  // Played from this Mac's copies: the viewer has to seek in them (see ShelfCache).
  ipcMain.handle(IPC.projectGraphics, async () =>
    Promise.all((await service.graphics()).map(async (graphic) => ({ ...graphic, url: await shelf.local(graphic.url) })))
  )
  ipcMain.handle(IPC.projectMusic, (_event, query: unknown) => service.music(typeof query === 'string' ? query.slice(0, 60) : ''))
  ipcMain.handle(IPC.projectAddMusic, (_event, id: unknown) => service.addMusic(String(id).slice(0, 64)))
  ipcMain.handle(IPC.projectBroll, (_event, query: unknown) => service.broll(typeof query === 'string' ? query.slice(0, 60) : ''))
  ipcMain.handle(IPC.projectAddBroll, (_event, id: unknown) => service.addBroll(String(id).slice(0, 500)))
  ipcMain.handle(IPC.projectSounds, (_event, query: unknown) => service.sounds(typeof query === 'string' ? query.slice(0, 100) : ''))
  ipcMain.handle(IPC.projectRetryAnalysis, (_event, assetId: unknown) => {
    if (typeof assetId !== 'string') throw new Error('assetId is required')
    return service.retryAnalysis(assetId)
  })
  return service
}
