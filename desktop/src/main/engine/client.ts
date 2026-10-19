import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process'
import { createInterface } from 'node:readline'

export class EngineError extends Error {
  constructor(
    readonly code: string,
    message: string
  ) {
    super(message)
  }
}

export interface EngineJob<T> {
  id: number
  result: Promise<T>
  cancel(): void
}

export interface RequestOptions {
  onProgress?(fraction: number): void
}

/** The part of the client the media library needs; tests pass a fake. */
export interface Engine {
  request<T>(method: string, params?: Record<string, unknown>, options?: RequestOptions): EngineJob<T>
}

interface Pending {
  resolve(value: unknown): void
  reject(error: Error): void
  onProgress?(fraction: number): void
}

interface Message {
  id?: number
  event?: string
  result?: unknown
  error?: { code: string; message: string }
  params?: { fraction?: number }
}

/**
 * Talks to clipnera-engine over stdio, one JSON object per line. Starts the process on the
 * first request and again after it exits, so a crash fails only the requests in flight.
 */
export class EngineClient implements Engine {
  private child: ChildProcessWithoutNullStreams | null = null
  private readonly pending = new Map<number, Pending>()
  private nextId = 1

  constructor(private readonly binary: string) {}

  request<T>(method: string, params: Record<string, unknown> = {}, options: RequestOptions = {}): EngineJob<T> {
    const id = this.nextId++
    const result = new Promise<T>((resolve, reject) => {
      this.pending.set(id, { resolve: resolve as (value: unknown) => void, reject, onProgress: options.onProgress })
    })
    try {
      this.process().stdin.write(`${JSON.stringify({ id, method, params })}\n`)
    } catch (error) {
      this.settle(id, new EngineError('ENGINE_UNAVAILABLE', (error as Error).message))
    }
    return { id, result, cancel: () => void this.request('cancel', { job: id }).result.catch(() => undefined) }
  }

  dispose(): void {
    this.child?.kill()
  }

  private process(): ChildProcessWithoutNullStreams {
    if (this.child) return this.child
    const child = spawn(this.binary, [], { stdio: ['pipe', 'pipe', 'pipe'] })
    this.child = child
    createInterface({ input: child.stdout }).on('line', (line) => this.receive(line))
    const failAll = (reason: string) => {
      if (this.child === child) this.child = null
      for (const id of [...this.pending.keys()]) this.settle(id, new EngineError('ENGINE_EXITED', reason))
    }
    child.on('error', (error) => failAll(`The video engine couldn't start: ${error.message}`))
    // A write after the engine died fails here instead of crashing the app; failAll reports it.
    child.stdin.on('error', () => undefined)
    child.on('exit', (code) => failAll(`The video engine stopped (exit code ${code}).`))
    return child
  }

  private receive(line: string): void {
    let message: Message
    try {
      message = JSON.parse(line) as Message
    } catch {
      return
    }
    if (message.id === undefined) return
    const pending = this.pending.get(message.id)
    if (!pending) return
    if (message.event === 'progress') return pending.onProgress?.(message.params?.fraction ?? 0)
    if (message.error) return this.settle(message.id, new EngineError(message.error.code, message.error.message))
    this.pending.delete(message.id)
    pending.resolve(message.result)
  }

  private settle(id: number, error: Error): void {
    this.pending.get(id)?.reject(error)
    this.pending.delete(id)
  }
}
