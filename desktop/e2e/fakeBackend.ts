import { createHash, randomUUID } from 'node:crypto'
import { createServer, type IncomingMessage, type Server, type ServerResponse } from 'node:http'
import { readFileSync } from 'node:fs'
import type { AddressInfo } from 'node:net'
import { join } from 'node:path'
import { applyOps, itemFrames, normalise, TimelineError, type Timeline } from '../../frontend/lib/editor/timeline'

export const USER = { id: 'user-1', name: 'Test Creator', email: 'creator@example.com', plan: 'pro', ai_credits_minutes_remaining: 1240 }

interface Analysis {
  asset_id: string
  polls: number
}

/** What the fake AI "finds" in every file, in the backend's AnalysisFindings shape. */
export const FINDINGS = {
  kind: 'video',
  duration: 3,
  summary: 'A colourful test card with a steady tone.',
  topics: ['testing'],
  language: 'en',
  words: 42,
  fillers: 3,
  dead_air: 0.5,
  shots: 1,
  tempo_bpm: null,
  chapters: [{ t0: 1, t1: 2, text: 'Someone says hello to their friends' }],
  problems: [],
  suggestions: ['Edit the full video.']
}

interface Project {
  id: string
  analysis: Analysis[]
  title: string
  version: number
  timeline: Timeline
  undo: Timeline[]
  redo: Timeline[]
  updated_at: string
}

export interface FakeBackend {
  url: string
  /** Every agent request body, to check what the app sent. */
  agentRequests: Record<string, unknown>[]
  /** Voice notes received: their size, whether they are WebM, and the seconds sent with them. */
  voiceNotes: { bytes: number; webm: boolean; seconds: number }[]
  /** Shelf shots copied into a project, by id. */
  brollAdded: string[]
  /** The X-Anthropic-Key each agent request carried (a person's own key), or null. */
  agentKeys: (string | null)[]
  /** Studio agent tools the person's own Claude called through the app: name and request body. */
  agentToolRuns: { name: string; body: Record<string, unknown> }[]
  calls: string[]
  /** Bytes received per uploaded key. */
  uploads: Map<string, number>
  projects: Map<string, Project>
  close(): Promise<void>
}

/** What the fake renderer hands back as the finished video. */
export const RENDERED = Buffer.from('fake finished video '.repeat(5000))

/** A short playable tone as a 16-bit mono WAV, for the fake sound library. */
function tone(seconds: number): Buffer {
  const rate = 22050
  const samples = Math.round(rate * seconds)
  const data = Buffer.alloc(samples * 2)
  for (let i = 0; i < samples; i++) data.writeInt16LE(Math.round(Math.sin((i / rate) * 2 * Math.PI * 440) * 8000), i * 2)
  const head = Buffer.alloc(44)
  head.write('RIFF', 0); head.writeUInt32LE(36 + data.length, 4); head.write('WAVEfmt ', 8); head.writeUInt32LE(16, 16)
  head.writeUInt16LE(1, 20); head.writeUInt16LE(1, 22); head.writeUInt32LE(rate, 24); head.writeUInt32LE(rate * 2, 28)
  head.writeUInt16LE(2, 32); head.writeUInt16LE(16, 34); head.write('data', 36); head.writeUInt32LE(data.length, 40)
  return Buffer.concat([head, data])
}
const SOUND_FILE = tone(0.6)

/** The fake sound library, in the backend's LibrarySound shape (urls are paths under the API host). */
export const SOUNDS = [
  { id: 'whoosh', name: 'Whoosh', tags: ['transition'], seconds: 0.6, url: '/static/sfx/whoosh.wav', licence: 'CC0', category: 'transition' },
  { id: 'sparkle', name: 'Sparkle', tags: ['magic'], seconds: 0.6, url: '/static/sfx/sparkle.wav', licence: 'CC0', category: 'ui' }
]

/** edit_engine/looks.py, as GET /editor/looks lists them. */
export const LOOKS = [
  { id: 'natural', label: 'Natural' }, { id: 'clean_bright', label: 'Clean & bright' }, { id: 'warm_film', label: 'Warm film' },
  { id: 'teal_orange', label: 'Teal & orange' }, { id: 'moody', label: 'Moody' }, { id: 'vivid', label: 'Vivid' }, { id: 'bw_punch', label: 'Black & white' }
]

/** Two caption styles in the backend's CaptionStyleOption shape. */
const LOOK = { font_family: 'Montserrat ExtraBold', font_size: 68, font_color: '#FFFFFF', highlight_color: '#7CF25A', emphasis_color: null, stroke_color: '#000000', stroke_width: 4, uppercase: true, background: false, background_color: null, max_words_per_line: 3, position_y: 0.76, animation: 'karaoke' }
export const CAPTION_STYLES = [
  { id: 'karaoke', name: 'Karaoke', description: 'Words light up as they are said', look: { ...LOOK, name: 'Karaoke' } },
  { id: 'simple', name: 'Simple', description: 'Plain white', look: { ...LOOK, name: 'Simple', highlight_color: '#FFFFFF', font_family: 'Roboto' } }
]
/** What the fake transcript says, in timeline seconds. */
export const SPOKEN = [{ word: 'hello', start: 0.1, end: 0.6 }, { word: 'there', start: 0.65, end: 1.1 }, { word: 'friends', start: 1.15, end: 1.6 }]

const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

/** A PlanCard (brain/schema.py) with one step. */
const card = (id: string, status: string) => ({
  id, status, title: 'Full edit', summary: 'Keep the strongest half', result_line: '0:01.5 · 1 step', credits: 4, credits_charged: 0,
  steps: [{ id: 's1', kind: 'tighten', intent: 'Cut the weaker half', why: '', enabled: true, optional: false, status: status === 'done' ? 'done' : 'pending', credits: 4, depends_on: [], note: status === 'done' ? 'Cut the second half' : '', undo_step_id: null }],
  assumptions: [], warnings: [], premium: [], ghost: [],
  outline: [{ start: 0, end: 1.5, said: '“hello there friends”', actions: ['1 cut (2 s of pauses, fillers and retakes out)', 'Closer shot at 0:01'] }],
  fps: 30, runner_up_title: null, error: null
})

const readBody = async (req: IncomingMessage) => {
  const chunks: Buffer[] = []
  for await (const chunk of req) chunks.push(chunk as Buffer)
  return Buffer.concat(chunks)
}

/**
 * Speaks the same contract as the backend's auth (desktop sign-in), /me and /editor routes.
 * Ops run through the shared applyOps the backend's fixtures check, so edits behave the same.
 */
export async function startFakeBackend(): Promise<FakeBackend> {
  const calls: string[] = []
  const uploads = new Map<string, number>()
  const brollAdded: string[] = []
  const agentKeys: (string | null)[] = []
  const agentToolRuns: FakeBackend['agentToolRuns'] = []
  const projects = new Map<string, Project>()
  const agentRequests: Record<string, unknown>[] = []
  const voiceNotes: FakeBackend['voiceNotes'] = []
  const plans = new Map<string, { projectId: string; status: string }>()
  const renders = new Map<string, number>()
  let style = [{ key: 'captions.style', label: 'Caption style', value: 'Karaoke', confidence: 0.8, in_use: true }]
  let pending: { challenge: string; port: number } | null = null
  const token = 'e2e-token'

  const json = (res: ServerResponse, status: number, body: unknown) => res.writeHead(status, { 'Content-Type': 'application/json' }).end(JSON.stringify(body))
  const ok = (res: ServerResponse, data: unknown) => json(res, 200, { data, message: null, error: null })
  const fail = (res: ServerResponse, status: number, error: string, message: string) => json(res, status, { error, message })
  const view = (p: Project) => ({ id: p.id, title: p.title, version: p.version, duration_s: 0, created_at: p.updated_at, updated_at: p.updated_at, timeline: p.timeline, asset_urls: {} })
  const commit = (p: Project, timeline: Timeline) => {
    p.timeline = timeline
    p.version += 1
    p.updated_at = new Date().toISOString()
    return { version: p.version, timeline }
  }

  const server: Server = createServer(async (req, res) => {
    const url = new URL(req.url ?? '/', 'http://127.0.0.1')
    const path = url.pathname
    calls.push(`${req.method} ${path}`)
    const body = req.method === 'POST' || req.method === 'PUT' ? await readBody(req) : Buffer.alloc(0)
    const input = () => (body.length ? JSON.parse(body.toString()) : {})
    const authorized = req.headers.authorization === `Bearer ${token}`

    if (path === '/api/v1/auth/desktop/start') {
      pending = { challenge: input().code_challenge, port: input().redirect_port }
      return ok(res, { authorize_url: `${base}/fake-google` })
    }
    if (path === '/fake-google') return res.writeHead(302, { Location: `${base}/api/v1/auth/desktop/callback?code=google-code` }).end()
    if (path === '/api/v1/auth/desktop/callback') return res.writeHead(302, { Location: `http://127.0.0.1:${pending?.port}/callback?code=one-time` }).end()
    if (path === '/api/v1/auth/desktop/exchange') {
      const challenge = createHash('sha256').update(input().code_verifier ?? '').digest('base64url')
      if (input().code !== 'one-time' || challenge !== pending?.challenge) return fail(res, 400, 'DESKTOP_CODE_INVALID', 'bad code')
      return ok(res, { access_token: token, token_type: 'bearer', expires_in: 3600 })
    }
    if (path.startsWith('/static/broll/')) {
      const file = readFileSync(join(__dirname, '../../broll_library', decodeURIComponent(path.slice('/static/broll/'.length))))
      return res.writeHead(200, { 'Content-Type': 'video/mp4', 'Content-Length': file.length }).end(file)
    }
    if (path.startsWith('/static/graphics/')) {
      // The real shelf's file, so the viewer draws a real packed-alpha graphic.
      const file = readFileSync(join(__dirname, '../../backend/static/motion/hook_graphics', path.split('/').pop()!))
      return res.writeHead(200, { 'Content-Type': 'video/mp4', 'Content-Length': file.length }).end(file)
    }
    if (path.startsWith('/static/sfx/')) return res.writeHead(200, { 'Content-Type': 'audio/wav', 'Content-Length': SOUND_FILE.length }).end(SOUND_FILE)
    if (path === '/renders/edit.mp4') return res.writeHead(200, { 'Content-Type': 'video/mp4', 'Content-Length': RENDERED.length }).end(RENDERED)
    if (path.startsWith('/upload/') && req.method === 'PUT') {
      if (Number(req.headers['content-length']) !== body.length) return fail(res, 400, 'BAD_LENGTH', 'Content-Length must match')
      uploads.set(decodeURIComponent(path.slice('/upload/'.length)), body.length)
      return res.writeHead(200).end()
    }
    if (!authorized) return fail(res, 401, 'UNAUTHORIZED', 'Not signed in')
    if (path === '/api/v1/me') return json(res, 200, USER)
    if (path === '/api/v1/auth/logout') return json(res, 200, { message: 'Logged out successfully' })

    if (path === '/api/v1/editor/sounds') {
      const q = (url.searchParams.get('q') ?? '').toLowerCase()
      const results = SOUNDS.filter((s) => !q || s.id.includes(q))
      return ok(res, { results, count: results.length, has_more: false })
    }
    if (path === '/api/v1/editor/voice') {
      // Multipart: an "audio" file and a "seconds" field, like brain/api.py voice_note.
      const text = body.toString('latin1')
      const seconds = Number(/name="seconds"\r\n\r\n([\d.]+)/.exec(text)?.[1])
      const at = body.indexOf(Buffer.from([0x1a, 0x45, 0xdf, 0xa3]))
      voiceNotes.push({ bytes: body.length, webm: at >= 0, seconds })
      if (!(at >= 0) || !seconds) return fail(res, 400, 'VOICE_TYPE', 'Not a voice note')
      return ok(res, { text: 'make it punchier' })
    }
    if (path === '/api/v1/editor/music') {
      return ok(res, [{ id: 'lofi_study', name: 'Lo-fi Study', mood: 'lofi', tags: ['lofi'], bpm: 82, seconds: 79, url: '/static/music/lofi_study.m4a', licence: 'Clipnera original, composed in code' }])
    }
    if (path === '/api/v1/editor/music/add') {
      const { project_id, id } = input()
      if (!projects.has(project_id) || id !== 'lofi_study') return fail(res, 404, 'NOT_FOUND', 'no such track')
      return ok(res, { key: `editor/${USER.id}/${project_id}/${randomUUID()}.m4a`, seconds: 79 })
    }
    if (path.startsWith('/static/music/')) {
      const file = readFileSync(join(__dirname, '../../backend/static/motion/music', path.split('/').pop()!))
      return res.writeHead(200, { 'Content-Type': 'audio/mp4', 'Content-Length': file.length }).end(file)
    }
    if (path === '/api/v1/editor/broll') {
      // One real public-domain shot from the shelf.
      return ok(res, [{ id: 'technology/3d-printer/science-launching-to-space-station-on-nasa-s-20th-nasa-ng-20-science-overview-shot1/science-launching-to-space-station-on-nasa-s-20th-nasa-ng-20-science-overview-shot1.mp4', title: 'Rocket Launch', category: 'science', topic: 'rocket', seconds: 5, url: '/static/broll/technology/3d-printer/science-launching-to-space-station-on-nasa-s-20th-nasa-ng-20-science-overview-shot1/science-launching-to-space-station-on-nasa-s-20th-nasa-ng-20-science-overview-shot1.mp4', licence: 'pd_us_gov', credit: 'Courtesy NASA' }])
    }
    if (path === '/api/v1/editor/broll/add') {
      const { project_id, id } = input()
      if (!projects.has(project_id) || !String(id).endsWith('.mp4')) return fail(res, 404, 'NOT_FOUND', 'no such shot')
      brollAdded.push(id)
      return ok(res, { key: `editor/${USER.id}/${project_id}/${randomUUID()}.mp4`, seconds: 5, width: 1920, height: 1080 })
    }
    if (path === '/api/v1/editor/graphics') return ok(res, [{ id: 'flash_burst', name: 'Flash Burst', seconds: 1, moods: ['hype'], url: '/static/graphics/flash_burst.mp4' }])
    if (path === '/api/v1/editor/caption-styles') return ok(res, CAPTION_STYLES)
    if (path === '/api/v1/editor/looks') return ok(res, LOOKS)
    if (path === '/api/v1/editor/style') return ok(res, style)
    if (path.startsWith('/api/v1/editor/style/') && req.method === 'DELETE') {
      const key = decodeURIComponent(path.slice('/api/v1/editor/style/'.length))
      style = style.filter((p) => p.key !== key)
      return ok(res, style)
    }
    if (path === '/api/v1/editor/agent-tools') {
      return ok(res, [
        { name: 'editing_playbook', description: 'How a professional editor works.', input_schema: { type: 'object', properties: {}, additionalProperties: false } },
        { name: 'apply_edits', description: 'Change the project with Timeline operations.', input_schema: { type: 'object', properties: { base_version: { type: 'integer' }, label: { type: 'string' }, ops: { type: 'array' } }, required: ['base_version', 'label', 'ops'], additionalProperties: false } },
        { name: 'look_at_frames', description: 'See the picture at timeline times.', input_schema: { type: 'object', properties: { times: { type: 'array' } }, required: ['times'], additionalProperties: false } }
      ])
    }
    if (path === '/api/v1/editor/models') return ok(res, { models: ['gpt-4o-mini', 'gpt-6-astra-1'], default_model: 'gpt-4o-mini', efforts: ['low', 'medium', 'high'] })

    const planMatch = /^\/api\/v1\/editor\/plans\/([^/]+)\/(approve|reject|stop|stream)$/.exec(path)
    if (planMatch) {
      const [, planId, action] = planMatch
      const plan = plans.get(planId)
      if (!plan) return fail(res, 404, 'NOT_FOUND', planId)
      if (action !== 'stream') {
        plan.status = action === 'approve' ? 'approved' : action === 'reject' ? 'rejected' : 'stopped'
        return ok(res, card(planId, plan.status))
      }
      // The plan runs: its one step trims the first clip to its first half.
      res.writeHead(200, { 'Content-Type': 'text/event-stream' })
      const p = projects.get(plan.projectId)!
      const first = p.timeline.tracks[0].items[0]
      res.write(sse('plan.updated', card(planId, 'running')))
      if (first?.type === 'clip') {
        p.undo.push(p.timeline)
        commit(p, applyOps(p.timeline, [{ op: 'trim_item', item: first.id, src_out: Math.floor((first.src_in + first.src_out) / 2) }]))
        res.write(sse('op.applied', { version: p.version, cursor: { author: 'agent:tighten', items: [first.id] } }))
      }
      res.write(sse('agent.step', { step_id: 's1', status: 'done', note: 'Cut the second half' }))
      res.write(sse('plan.updated', card(planId, 'done')))
      res.write(sse('done', { status: 'done' }))
      return res.end()
    }

    if (path === '/api/v1/editor/projects' && req.method === 'GET') return ok(res, [...projects.values()].map((p) => ({ ...view(p), timeline: undefined, asset_urls: undefined })))
    if (path === '/api/v1/editor/projects' && req.method === 'POST') {
      const id = randomUUID()
      const timeline = normalise({ fps: 30, width: 1920, height: 1080, tracks: [{ id: 'v1', kind: 'video', items: [] }] })
      const p: Project = { id, analysis: [], title: input().title ?? 'Untitled project', version: 0, timeline, undo: [], redo: [], updated_at: new Date().toISOString() }
      projects.set(id, p)
      return ok(res, view(p))
    }

    const match = /^\/api\/v1\/editor\/projects\/([^/]+)(?:\/(.+))?$/.exec(path)
    const p = match && projects.get(match[1])
    if (!match || !p) return fail(res, 404, 'NOT_FOUND', path)
    const action = match[2]

    if (!action) return ok(res, view(p))
    if (action === 'ops') {
      const { base_version, ops } = input()
      if (base_version > p.version) return fail(res, 409, 'STALE_VERSION', 'stale')
      try {
        const next = applyOps(p.timeline, ops)
        for (const op of ops) if (op.op === 'add_asset') p.analysis.push({ asset_id: op.asset.id, polls: 0 })
        p.undo.push(p.timeline)
        p.redo = []
        return ok(res, commit(p, next))
      } catch (error) {
        return fail(res, 422, error instanceof TimelineError ? error.code : 'BAD_OPS', (error as Error).message)
      }
    }
    if (action === 'undo' || action === 'redo') {
      const from = action === 'undo' ? p.undo : p.redo
      const to = action === 'undo' ? p.redo : p.undo
      const previous = from.pop()
      if (!previous) return fail(res, 409, 'NOTHING_TO_UNDO', `Nothing to ${action}`)
      to.push(p.timeline)
      return ok(res, commit(p, previous))
    }
    const toolMatch = /^agent-tools\/(.+)$/.exec(action)
    if (toolMatch) {
      const body = input()
      const name = decodeURIComponent(toolMatch[1])
      agentToolRuns.push({ name, body })
      const output = (text: string, images: string[] = [], is_error = false) => ok(res, { text, images, is_error, version: p.version })
      if (name === 'editing_playbook') return output('How a professional editor works')
      if (name === 'look_at_frames') return output('0:01: clip c1', ['/9j/4AAQSkZJRg=='])
      if (name !== 'apply_edits') return output(`There is no tool called ${name}.`, [], true)
      try {
        p.undo.push(p.timeline)
        commit(p, applyOps(p.timeline, body.arguments.ops))
        return output(JSON.stringify({ undo_step_id: 'claude-1-1', version: p.version }))
      } catch (error) {
        p.undo.pop()
        return output((error as Error).message, [], true)
      }
    }
    if (action === 'agent') {
      const request = input()
      agentRequests.push(request)
      agentKeys.push(typeof req.headers['x-anthropic-key'] === 'string' ? req.headers['x-anthropic-key'] : null)
      res.writeHead(200, { 'Content-Type': 'text/event-stream' })
      const send = (event: string, data: unknown) => res.write(sse(event, data))
      if (String(request.prompt).toLowerCase().includes('full edit')) {
        // A whole edit becomes a plan for the person to approve.
        const planId = randomUUID()
        plans.set(planId, { projectId: p.id, status: 'proposed' })
        send('tool', { id: 'plan', name: 'plan_edit', label: 'Planning the edit' })
        send('plan', card(planId, 'proposed'))
        send('tool_done', { id: 'plan', ok: true, error: null })
        send('done', { reason: 'handed_over', message: null })
        return res.end()
      }
      // A small edit: read the timeline, split the first clip in the middle, show it.
      send('tool', { id: 't1', name: 'get_timeline', label: 'Reading the timeline' })
      await new Promise((r) => setTimeout(r, 300))
      send('tool_done', { id: 't1', ok: true, error: null })
      const first = p.timeline.tracks[0].items[0]
      if (first) {
        send('tool', { id: 't2', name: 'apply_edits', label: 'Splitting the clip' })
        const middle = first.at + Math.floor(itemFrames(first) / 2)
        p.undo.push(p.timeline)
        commit(p, applyOps(p.timeline, [{ op: 'split_item', item: first.id, at: middle, new_id: 'ai-piece' }]))
        send('tool_done', { id: 't2', ok: true, error: null })
        send('edit', { label: 'Split the clip in two', version: p.version, undo_step_id: 'turn-1-1' })
        send('ui', { action: 'seek', seconds: middle / p.timeline.fps, end: null, item_ids: [], panel: null })
        send('ui', { action: 'select', seconds: null, end: null, item_ids: ['ai-piece'], panel: null })
      }
      send('text', { text: 'I split the clip in the middle and selected the second half.' })
      send('done', { reason: 'answered', message: null })
      return res.end()
    }
    if (action === 'renders' && req.method === 'POST') {
      const id = randomUUID()
      renders.set(id, 0)
      return ok(res, { id, status: 'queued', stage: '', version: p.version, download_url: null, error: null })
    }
    if (action.startsWith('renders/')) {
      // queued → rendering → done, one step per look.
      const id = action.slice('renders/'.length)
      const step = (renders.get(id) ?? 0) + 1
      renders.set(id, step)
      const status = step === 1 ? 'rendering' : 'done'
      return ok(res, { id, status, stage: status === 'rendering' ? 'captions' : 'done', version: p.version, download_url: status === 'done' ? `${base}/renders/edit.mp4` : null, error: null })
    }
    if (action.startsWith('steps/') && action.endsWith('/undo')) {
      const previous = p.undo.pop()
      if (!previous) return fail(res, 409, 'NOTHING_TO_UNDO', 'Nothing to undo')
      p.redo.push(p.timeline)
      return ok(res, commit(p, previous))
    }
    if (action === 'preview') {
      // Like brain/preview.py: captions only when on; titles in the renderer's three kinds.
      const t = p.timeline
      const style = t.captions?.enabled ? t.captions.style : null
      const texts = t.tracks.flatMap((tr) => tr.items).flatMap((i) => (i.type === 'text' ? [{ kind: i.at === 0 && i.transform.y < 0.45 ? 'hook' : i.transform.y > 0.6 ? 'line' : 'pop', text: i.text, at: i.at / t.fps, dur: i.dur / t.fps }] : []))
      const look = CAPTION_STYLES.find((c) => c.id === style)?.look ?? (style ? CAPTION_STYLES[0].look : null)
      return ok(res, { version: p.version, look: t.look, caption_style: style, caption_look: look, words: style ? SPOKEN : [], texts, sounds: [] })
    }
    if (action === 'analysis') {
      // Each look moves a file on: pending → running (listening) → ready.
      return ok(
        res,
        p.analysis.map((a) => {
          const step = a.polls++
          const status = step === 0 ? 'pending' : step === 1 ? 'running' : 'ready'
          return { asset_id: a.asset_id, status, stage: status === 'running' ? 'transcript' : null, findings: status === 'ready' ? FINDINGS : null, error: null, updated_at: new Date().toISOString() }
        })
      )
    }
    if (action === 'assets/init') {
      const { filename, content_type } = input()
      const key = `editor/${USER.id}/${p.id}/${randomUUID()}${filename.slice(filename.lastIndexOf('.'))}`
      return ok(res, { key, url: `${base}/upload/${encodeURIComponent(key)}`, content_type })
    }
    return fail(res, 404, 'NOT_FOUND', path)
  })

  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
  const base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`
  return { url: base, calls, uploads, projects, agentRequests, voiceNotes, brollAdded, agentKeys, agentToolRuns, close: () => new Promise((resolve) => server.close(() => resolve())) }
}
