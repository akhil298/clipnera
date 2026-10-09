/**
 * Pure pieces of the event stream: the SSE line parser, event parsing, backoff and the
 * "give up on SSE for a while" rule. No browser APIs here, so node --test covers it all.
 */
import type { RealtimeEvent } from './events';

export interface SseMessage {
  /** The last `id:` seen on the stream (it carries over to later messages, per the SSE spec). */
  id: string;
  event: string;
  data: string;
}

export interface SseCallbacks {
  onMessage: (message: SseMessage) => void;
  /** A `retry:` field, in ms. */
  onRetry?: (ms: number) => void;
}

/**
 * Incremental `text/event-stream` parser. Accepts LF, CRLF and CR line endings, including a CRLF split
 * across chunks (events.md §1.3). Comments (`: hb`) are skipped; any bytes count as liveness upstream.
 */
export function createSseParser({ onMessage, onRetry }: SseCallbacks) {
  let buffer = '';
  let lastId = '';
  let event = '';
  let data: string[] = [];
  let skipLeadingLf = false;

  const dispatch = () => {
    if (data.length) onMessage({ id: lastId, event: event || 'message', data: data.join('\n') });
    event = '';
    data = [];
  };

  const line = (text: string) => {
    if (text === '') return dispatch();
    if (text.startsWith(':')) return;
    const colon = text.indexOf(':');
    const field = colon === -1 ? text : text.slice(0, colon);
    let value = colon === -1 ? '' : text.slice(colon + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'data') data.push(value);
    else if (field === 'event') event = value;
    else if (field === 'id' && !value.includes('\0')) lastId = value;
    else if (field === 'retry' && /^\d+$/.test(value)) onRetry?.(Number(value));
  };

  return {
    push(chunk: string) {
      buffer += chunk;
      if (skipLeadingLf && buffer.startsWith('\n')) buffer = buffer.slice(1);
      skipLeadingLf = false;
      let start = 0;
      for (let i = 0; i < buffer.length; i++) {
        const ch = buffer[i];
        if (ch !== '\n' && ch !== '\r') continue;
        line(buffer.slice(start, i));
        if (ch === '\r') {
          if (i + 1 === buffer.length) skipLeadingLf = true;
          else if (buffer[i + 1] === '\n') i++;
        }
        start = i + 1;
      }
      buffer = buffer.slice(start);
    },
    get lastEventId() {
      return lastId;
    },
  };
}

/**
 * One event from an SSE `data:` payload or a poll item. Accepts frontend.md's `topic` for `stream`.
 * Returns null for anything that isn't an event object (the stream carries on).
 */
export function parseEvent(raw: unknown): RealtimeEvent | null {
  let value = raw;
  if (typeof value === 'string') {
    try {
      value = JSON.parse(value);
    } catch {
      return null;
    }
  }
  if (typeof value !== 'object' || value === null) return null;
  const record = value as Record<string, unknown>;
  const stream = typeof record.stream === 'string' ? record.stream : record.topic;
  if (typeof record.type !== 'string' || typeof stream !== 'string') return null;
  return {
    ...record,
    type: record.type,
    stream,
    v: typeof record.v === 'number' ? record.v : 1,
    seq: typeof record.seq === 'number' ? record.seq : 0,
    durable: record.durable !== false,
    ts: typeof record.ts === 'string' ? record.ts : '',
    data: record.data ?? {},
  } as RealtimeEvent;
}

export const RECONNECT_BASE_MS = 3_000;
export const RECONNECT_CAP_MS = 30_000;

/** Exponential backoff with equal jitter (half fixed, half random), capped (events.md §1.3). */
export function backoffDelay(attempt: number, baseMs = RECONNECT_BASE_MS, capMs = RECONNECT_CAP_MS, random = Math.random): number {
  const ceiling = Math.min(capMs, baseMs * 2 ** Math.max(0, attempt));
  return Math.round(ceiling / 2 + (ceiling / 2) * random());
}

/** events.md §7.3 step 6: three failed SSE attempts within 60 s switch to long polling. */
export const FALLBACK_AFTER_FAILURES = 3;
export const FALLBACK_WINDOW_MS = 60_000;

export function createFailureWindow(limit = FALLBACK_AFTER_FAILURES, windowMs = FALLBACK_WINDOW_MS) {
  let failures: number[] = [];
  return {
    /** Records a failure at `now`; true when SSE should give way to polling. */
    fail(now: number): boolean {
      failures = [...failures.filter((at) => now - at < windowMs), now];
      return failures.length >= limit;
    },
    reset() {
      failures = [];
    },
  };
}
