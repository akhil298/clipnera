/**
 * One event stream per signed-in browser (docs/revamp/architecture/frontend.md §4, events.md §7).
 *
 * - SSE over `fetch` (EventSource can't send the bearer token), resuming with `Last-Event-ID`.
 * - Reconnects with jittered backoff; a 45 s silence (no event, no heartbeat) counts as a failure.
 * - Three failures in 60 s switch to `GET /events/poll` long polling, and SSE is retried every 2 min.
 * - Web Locks pick one leader tab that holds the connection and fans events out over
 *   `BroadcastChannel('cn-events')`; without those APIs every tab connects on its own.
 * - The stream is open while anything holds it (`subscribe` or `hold`), and closes 10 s after the last release.
 *
 * NEEDS-BACKEND: `GET /events/stream` and `GET /events/poll` don't exist yet. A 404 marks the
 * stream `down` (queries fall back to polling, see `useFallbackInterval`) and it is retried every 2 min.
 */
import { apiFetch, apiUrl, endSession } from '@/lib/api/client';
import { isNotFound, isUnauthorized } from '@/lib/api/errors';
import { getToken } from '@/lib/auth';

import { type RealtimeEvent, type RealtimeHandler, type RealtimeStatus } from './events';
import { backoffDelay, createFailureWindow, createSseParser, parseEvent, RECONNECT_BASE_MS, type SseMessage } from './protocol';
import { createRouter } from './router';

const STALL_MS = 45_000;
const SSE_RETRY_MS = 2 * 60_000;
const POLL_WAIT_S = 25;
const RELEASE_GRACE_MS = 10_000;
const LOCK_NAME = 'cn-events';
const CHANNEL_NAME = 'cn-events';

type Outcome = 'ok' | 'dropped' | 'failed' | 'missing' | 'unauthorized' | 'aborted';

type TabMessage =
  | { kind: 'event'; id: string; event: RealtimeEvent }
  | { kind: 'status'; status: RealtimeStatus }
  | { kind: 'hello' };

interface PollPage {
  events: unknown[];
  cursor: string;
  /** The cursor is older than the server's buffer: refetch snapshots. */
  reset?: boolean;
}

export class RealtimeClient {
  private readonly router = createRouter();
  private readonly statusListeners = new Set<() => void>();
  private status: RealtimeStatus = 'idle';
  private holds = 0;
  private started = false;
  private leader = false;
  private lastEventId = '';
  private retryMs = RECONNECT_BASE_MS;
  private channel: BroadcastChannel | null = null;
  private lockRequest: AbortController | null = null;
  private releaseLock: (() => void) | null = null;
  private connection: AbortController | null = null;
  private releaseTimer: ReturnType<typeof setTimeout> | undefined;
  private wake: (() => void) | null = null;
  /** Bumped by every lead() and stop(), so a loop left over from before a restart exits. */
  private generation = 0;

  /** Listens to a topic (see router.ts) and keeps the stream open until the returned function runs. */
  subscribe(topic: string, handler: RealtimeHandler): () => void {
    const unsubscribe = this.router.subscribe(topic, handler);
    const release = this.hold();
    return () => {
      unsubscribe();
      release();
    };
  }

  /** Listens without keeping the stream open (the handlers/ registry). */
  listen(topic: string, handler: RealtimeHandler): () => void {
    return this.router.subscribe(topic, handler);
  }

  /** Keeps the stream open without listening (the app shell). */
  hold(): () => void {
    this.holds++;
    clearTimeout(this.releaseTimer);
    this.start();
    let released = false;
    return () => {
      if (released) return;
      released = true;
      if (--this.holds === 0) this.releaseTimer = setTimeout(() => this.stop(), RELEASE_GRACE_MS);
    };
  }

  getStatus = (): RealtimeStatus => this.status;

  onStatus = (listener: () => void): (() => void) => {
    this.statusListeners.add(listener);
    return () => this.statusListeners.delete(listener);
  };

  private setStatus(status: RealtimeStatus): void {
    if (status === this.status) return;
    this.status = status;
    if (this.leader) this.post({ kind: 'status', status });
    this.statusListeners.forEach((listener) => listener());
  }

  private start(): void {
    if (this.started || typeof window === 'undefined' || !getToken()) return;
    this.started = true;
    window.addEventListener('online', this.onOnline);
    this.setStatus('connecting');

    if (typeof BroadcastChannel === 'undefined' || !navigator.locks) {
      void this.lead();
      return;
    }
    this.channel = new BroadcastChannel(CHANNEL_NAME);
    this.channel.onmessage = ({ data }: MessageEvent<TabMessage>) => this.onTabMessage(data);
    this.lockRequest = new AbortController();
    navigator.locks
      .request(LOCK_NAME, { signal: this.lockRequest.signal }, () => new Promise<void>((resolve) => {
        this.releaseLock = resolve;
        void this.lead();
      }))
      .catch(() => undefined);
    this.post({ kind: 'hello' });
  }

  private stop(): void {
    if (!this.started) return;
    this.started = false;
    this.leader = false;
    this.generation++;
    window.removeEventListener('online', this.onOnline);
    this.connection?.abort();
    this.wake?.();
    this.releaseLock?.();
    this.releaseLock = null;
    this.lockRequest?.abort();
    this.lockRequest = null;
    this.channel?.close();
    this.channel = null;
    this.setStatus('idle');
  }

  private onOnline = () => this.wake?.();

  private onTabMessage(message: TabMessage): void {
    if (message.kind === 'hello') {
      if (this.leader) this.post({ kind: 'status', status: this.status });
    } else if (message.kind === 'status') {
      if (!this.leader) this.setStatus(message.status);
    } else {
      this.lastEventId = message.id || this.lastEventId;
      this.router.dispatch(message.event);
    }
  }

  private post(message: TabMessage): void {
    this.channel?.postMessage(message);
  }

  private deliver(event: RealtimeEvent, id: string): void {
    if (id) this.lastEventId = id;
    if (event.type === 'auth.expired') {
      this.stop();
      endSession();
      return;
    }
    this.router.dispatch(event);
    this.post({ kind: 'event', id, event });
  }

  /** The leader's loop: SSE, falling back to long polling, until stopped. */
  private async lead(): Promise<void> {
    this.leader = true;
    const generation = ++this.generation;
    this.post({ kind: 'status', status: this.status });
    const failures = createFailureWindow();
    let attempt = 0;
    let pollUntil = 0;

    while (generation === this.generation) {
      const polling = Date.now() < pollUntil;
      const outcome = polling ? await this.pollOnce() : await this.streamOnce();
      if (outcome === 'aborted' || generation !== this.generation) return;
      if (outcome === 'unauthorized') {
        const signedIn = !!getToken();
        this.stop();
        if (signedIn) endSession();
        return;
      }
      if (outcome === 'ok') {
        attempt = 0;
        continue;
      }
      this.setStatus('down');
      if (outcome === 'missing') {
        await this.sleep(SSE_RETRY_MS);
        continue;
      }
      if (outcome === 'dropped') attempt = 0;
      // A failed SSE retry while polling goes straight back to polling.
      if (!polling && (failures.fail(Date.now()) || pollUntil > 0)) pollUntil = Date.now() + SSE_RETRY_MS;
      await this.sleep(backoffDelay(attempt++, this.retryMs));
    }
  }

  private async streamOnce(): Promise<Outcome> {
    const token = getToken();
    if (!token) return 'unauthorized';
    const connection = (this.connection = new AbortController());
    let stalled = false;
    let watchdog: ReturnType<typeof setTimeout> | undefined;
    const touch = () => {
      clearTimeout(watchdog);
      watchdog = setTimeout(() => {
        stalled = true;
        connection.abort();
      }, STALL_MS);
    };

    this.setStatus('connecting');
    try {
      const headers: Record<string, string> = {
        Accept: 'text/event-stream',
        Authorization: `Bearer ${token}`,
        'X-Request-ID': crypto.randomUUID(),
      };
      if (this.lastEventId) headers['Last-Event-ID'] = this.lastEventId;
      touch();
      const res = await fetch(apiUrl('/events/stream'), { headers, credentials: 'include', cache: 'no-store', signal: connection.signal });
      if (res.status === 401) return 'unauthorized';
      if (res.status === 404) return 'missing';
      if (!res.ok || !res.body) return 'failed';

      this.setStatus('open');
      const parser = createSseParser({
        onMessage: (message: SseMessage) => {
          const event = parseEvent(message.data);
          if (event) this.deliver(event, message.id);
        },
        onRetry: (ms) => {
          this.retryMs = ms;
        },
      });
      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
      for (;;) {
        const { value, done } = await reader.read();
        if (done) return 'dropped';
        touch();
        parser.push(value);
      }
    } catch {
      return connection.signal.aborted && !stalled ? 'aborted' : 'failed';
    } finally {
      clearTimeout(watchdog);
    }
  }

  private async pollOnce(): Promise<Outcome> {
    const connection = (this.connection = new AbortController());
    try {
      const page = await apiFetch<PollPage>('/events/poll', {
        query: { cursor: this.lastEventId, wait: POLL_WAIT_S },
        timeoutMs: (POLL_WAIT_S + 10) * 1000,
        signal: connection.signal,
      });
      this.setStatus('polling');
      if (page.reset) this.deliver(resyncEvent(), '');
      for (const raw of page.events) {
        const event = parseEvent(raw);
        if (event) this.deliver(event, '');
      }
      this.lastEventId = page.cursor || this.lastEventId;
      return 'ok';
    } catch (error) {
      if (connection.signal.aborted) return 'aborted';
      if (isUnauthorized(error)) return 'unauthorized';
      return isNotFound(error) ? 'missing' : 'failed';
    }
  }

  /** Waits, unless stopped or the browser comes back online first. */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => {
      const done = () => {
        clearTimeout(timer);
        this.wake = null;
        resolve();
      };
      const timer = setTimeout(done, ms);
      this.wake = done;
    });
  }
}

/** What the poll fallback hands handlers when its cursor fell out of the server's buffer. */
function resyncEvent(): RealtimeEvent {
  return { type: 'sync.reset', v: 1, stream: 'user:self', seq: 0, durable: false, ts: new Date().toISOString(), data: { reason: 'buffer_miss' } };
}
