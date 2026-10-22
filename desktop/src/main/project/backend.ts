import { normalise, type Timeline, type TimelineOp } from '@timeline'
import type {
  AspectRatio,
  EditorAssetInitRequest,
  EditorAssetType,
  EditorAssetUpload,
  EditorOpsRequest,
  EditorOpsResponse,
  EditorProjectCreate,
  EditorProjectResponse,
  CaptionStyleOption,
  EditorProjectSummary,
  AgentToolOutput, AgentToolRun, AgentToolSpec,
  BrollAdded, LibraryBroll, LibraryGraphic, LibraryMusic, LibrarySound, MusicAdded,
  LookOption,
  MediaAnalysisResponse,
  ProjectPreview,
  SoundSearchResponse,
  StylePreference
} from '../../shared/api'
import type { ProjectSnapshot } from '../../shared/project'
import { API_URL, api } from '../api'
import { putFile } from './upload'

export interface UploadFile {
  path: string
  filename: string
  contentType: EditorAssetType
  size: number
}

/** Where a project lives: the Clipnera backend, or this Mac in preview mode. */
export interface ProjectBackend {
  /** Whether the AI can understand this project's footage (only on the Clipnera backend). */
  readonly understands: boolean
  /** The most recently edited project, or a new one when there is none. */
  openLatest(): Promise<ProjectSnapshot>
  get(id: string): Promise<ProjectSnapshot>
  apply(id: string, baseVersion: number, ops: TimelineOp[]): Promise<{ version: number; timeline: Timeline }>
  undo(id: string): Promise<{ version: number; timeline: Timeline }>
  redo(id: string): Promise<{ version: number; timeline: Timeline }>
  /** Stores a file for the project and returns the key to add it under with add_asset. */
  upload(id: string, file: UploadFile, onProgress: (fraction: number) => void): Promise<string>
  /** How far the AI has got understanding each asset. */
  analysis(id: string): Promise<MediaAnalysisResponse[]>
  retryAnalysis(id: string, assetId: string): Promise<MediaAnalysisResponse>
  /** What the export will draw over the picture. */
  preview(id: string, timeline: Timeline, version: number): Promise<ProjectPreview>
  captionStyles(): Promise<CaptionStyleOption[]>
  /** The sound effects library, with playable URLs. */
  sounds(query: string): Promise<LibrarySound[]>
  /** The animated graphics shelf, with playable URLs. */
  graphics(): Promise<LibraryGraphic[]>
  /** The public-domain B-roll shelf, with playable URLs, and copying a shot into a project. */
  broll(query: string): Promise<LibraryBroll[]>
  addBroll(projectId: string, id: string): Promise<BrollAdded>
  /** Clipnera's own music beds, with playable URLs, and copying one into a project. */
  music(query: string): Promise<LibraryMusic[]>
  addMusic(projectId: string, id: string): Promise<MusicAdded>
  looks(): Promise<LookOption[]>
  /** The studio agent's tools the person's own Claude may call, and calling one on a project. */
  agentTools(): Promise<AgentToolSpec[]>
  agentTool(projectId: string, name: string, run: AgentToolRun): Promise<AgentToolOutput>
  /** What the AI has learned from the user's corrections, and forgetting one of them. */
  style(): Promise<StylePreference[]>
  forgetStyle(key: string): Promise<StylePreference[]>
}

/** Full edits keep the footage's own shape, so new projects are landscape. */
export const NEW_PROJECT: EditorProjectCreate = { title: 'Untitled project', aspect: '16:9' satisfies AspectRatio }

// The backend stores timelines without their defaults; fill them so every field is present.
const snapshot = (p: EditorProjectResponse): ProjectSnapshot => ({ id: p.id, title: p.title, version: p.version, timeline: normalise(p.timeline), assetUrls: p.asset_urls })
/** The library's files are paths under the API host. */
export const absolute = (path: string) => (/^https?:/.test(path) ? path : `${API_URL}${path.startsWith('/') ? '' : '/'}${path}`)
const result = (r: EditorOpsResponse) => ({ version: r.version, timeline: normalise(r.timeline) })

export class RemoteProjectBackend implements ProjectBackend {
  readonly understands = true

  constructor(private readonly token: () => Promise<string | null>) {}

  async openLatest(): Promise<ProjectSnapshot> {
    const projects = await api.getData<EditorProjectSummary[]>('/editor/projects', await this.auth())
    const latest = [...projects].sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0]
    if (latest) return this.get(latest.id)
    return snapshot(await api.postData<EditorProjectResponse>('/editor/projects', NEW_PROJECT, await this.auth()))
  }

  async get(id: string): Promise<ProjectSnapshot> {
    return snapshot(await api.getData<EditorProjectResponse>(`/editor/projects/${id}`, await this.auth()))
  }

  async apply(id: string, baseVersion: number, ops: TimelineOp[]) {
    return result(await api.postData<EditorOpsResponse>(`/editor/projects/${id}/ops`, { base_version: baseVersion, ops } satisfies EditorOpsRequest, await this.auth()))
  }

  async undo(id: string) {
    return result(await api.postData<EditorOpsResponse>(`/editor/projects/${id}/undo`, {}, await this.auth()))
  }

  async redo(id: string) {
    return result(await api.postData<EditorOpsResponse>(`/editor/projects/${id}/redo`, {}, await this.auth()))
  }

  async upload(id: string, file: UploadFile, onProgress: (fraction: number) => void): Promise<string> {
    const init: EditorAssetInitRequest = { filename: file.filename, content_type: file.contentType, size_bytes: file.size }
    const target = await api.postData<EditorAssetUpload>(`/editor/projects/${id}/assets/init`, init, await this.auth())
    await putFile(target.url, file.path, target.content_type, file.size, onProgress)
    return target.key
  }

  async analysis(id: string): Promise<MediaAnalysisResponse[]> {
    return api.getData<MediaAnalysisResponse[]>(`/editor/projects/${id}/analysis`, await this.auth())
  }

  async retryAnalysis(id: string, assetId: string): Promise<MediaAnalysisResponse> {
    return api.postData<MediaAnalysisResponse>(`/editor/projects/${id}/analysis/${assetId}/retry`, {}, await this.auth())
  }

  async preview(id: string): Promise<ProjectPreview> {
    return api.getData<ProjectPreview>(`/editor/projects/${id}/preview`, await this.auth())
  }

  async captionStyles(): Promise<CaptionStyleOption[]> {
    return api.getData<CaptionStyleOption[]>('/editor/caption-styles', await this.auth())
  }

  async style(): Promise<StylePreference[]> {
    return api.getData<StylePreference[]>('/editor/style', await this.auth())
  }

  async forgetStyle(key: string): Promise<StylePreference[]> {
    return api.deleteData<StylePreference[]>(`/editor/style/${encodeURIComponent(key)}`, await this.auth())
  }

  async looks(): Promise<LookOption[]> {
    return api.getData<LookOption[]>('/editor/looks', await this.auth())
  }

  async sounds(query: string): Promise<LibrarySound[]> {
    const params = new URLSearchParams({ q: query, page_size: '100' })
    const found = await api.getData<SoundSearchResponse>(`/editor/sounds?${params}`, await this.auth())
    return found.results.map((sound) => ({ ...sound, url: absolute(sound.url) }))
  }

  async graphics(): Promise<LibraryGraphic[]> {
    const found = await api.getData<LibraryGraphic[]>('/editor/graphics', await this.auth())
    return found.map((graphic) => ({ ...graphic, url: absolute(graphic.url) }))
  }

  async broll(query: string): Promise<LibraryBroll[]> {
    const found = await api.getData<LibraryBroll[]>(`/editor/broll?${new URLSearchParams({ q: query })}`, await this.auth())
    return found.map((shot) => ({ ...shot, url: absolute(shot.url) }))
  }

  async addBroll(projectId: string, id: string): Promise<BrollAdded> {
    return api.postData<BrollAdded>('/editor/broll/add', { project_id: projectId, id }, await this.auth())
  }

  async music(query: string): Promise<LibraryMusic[]> {
    const found = await api.getData<LibraryMusic[]>(`/editor/music?${new URLSearchParams({ q: query })}`, await this.auth())
    return found.map((track) => ({ ...track, url: absolute(track.url) }))
  }

  async addMusic(projectId: string, id: string): Promise<MusicAdded> {
    return api.postData<MusicAdded>('/editor/music/add', { project_id: projectId, id }, await this.auth())
  }

  async agentTools(): Promise<AgentToolSpec[]> {
    return api.getData<AgentToolSpec[]>('/editor/agent-tools', await this.auth())
  }

  async agentTool(projectId: string, name: string, run: AgentToolRun): Promise<AgentToolOutput> {
    return api.postData<AgentToolOutput>(`/editor/projects/${projectId}/agent-tools/${encodeURIComponent(name)}`, run, await this.auth())
  }

  private async auth(): Promise<string> {
    const token = await this.token()
    if (!token) throw new Error('Sign in to open your projects')
    return token
  }
}
