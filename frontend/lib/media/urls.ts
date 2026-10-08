/**
 * Signed media URLs for the preview. The engine never knows an endpoint: the
 * caller injects a resolver (P2 wires it to the editor's asset query). URLs are
 * cached, refreshed shortly before they expire, and re-requested when a media
 * element fails on one (an expired S3 link shows up as a 403, which a media
 * element only reports as an error). Pure apart from the injected resolver.
 */
import type { Asset } from '../editor/timeline';

export type MediaRef =
  | { kind: 'asset'; asset: Asset }
  | { kind: 'music'; track: string }
  | { kind: 'sfx'; name: string };

export interface ResolvedUrl {
  url: string;
  /** Epoch ms; read from the URL's signature when the resolver leaves it out. */
  expiresAt?: number | null;
}

/** `refresh` is true when the cached URL failed or is about to expire: skip any cache upstream. */
export type UrlResolver = (ref: MediaRef, options: { refresh: boolean }) => Promise<ResolvedUrl | string>;

export const refKey = (ref: MediaRef): string =>
  ref.kind === 'asset' ? `asset:${ref.asset.id}:${ref.asset.proxy ?? ref.asset.key}` : ref.kind === 'music' ? `music:${ref.track}` : `sfx:${ref.name}`;

/**
 * When a signed URL stops working, from its query: S3 SigV4 (X-Amz-Date +
 * X-Amz-Expires, what backend/clients/services/s3.py signs), SigV2 and
 * CloudFront (`Expires`, epoch seconds). Null when it carries no expiry.
 */
export function expiryFromUrl(url: string): number | null {
  let params: URLSearchParams;
  try {
    params = new URL(url, 'http://local').searchParams;
  } catch {
    return null;
  }
  const date = params.get('X-Amz-Date');
  const seconds = params.get('X-Amz-Expires');
  if (date && seconds) {
    const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/.exec(date);
    if (m) return Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]) + Number(seconds) * 1000;
  }
  const expires = params.get('Expires');
  return expires && /^\d+$/.test(expires) ? Number(expires) * 1000 : null;
}

interface Entry {
  url: string;
  expiresAt: number | null;
  failures: number;
}

export interface MediaUrlsOptions {
  now?: () => number;
  /** Refresh this long before expiry. Default 60 s. */
  marginMs?: number;
  /** Give up on a ref after this many failed refreshes in a row. Default 2. */
  maxFailures?: number;
}

export class MediaUrlError extends Error {
  readonly ref: MediaRef;

  constructor(ref: MediaRef, cause?: unknown) {
    super(`Could not get a playable link for ${refKey(ref)}.`, { cause });
    this.name = 'MediaUrlError';
    this.ref = ref;
  }
}

export class MediaUrls {
  private readonly cache = new Map<string, Entry>();
  private readonly inflight = new Map<string, Promise<string>>();
  private readonly now: () => number;
  private readonly marginMs: number;
  private readonly maxFailures: number;
  private readonly resolver: UrlResolver;

  constructor(resolver: UrlResolver, options: MediaUrlsOptions = {}) {
    this.resolver = resolver;
    this.now = options.now ?? Date.now;
    this.marginMs = options.marginMs ?? 60_000;
    this.maxFailures = options.maxFailures ?? 2;
  }

  /** The cached URL right now, or null if none yet. A URL near expiry is still returned while a fresh one loads. */
  peek(ref: MediaRef): string | null {
    const entry = this.cache.get(refKey(ref));
    if (!entry) return null;
    if (this.expiring(entry)) void this.load(ref, true).catch(() => undefined);
    return this.expired(entry) ? null : entry.url;
  }

  /** A usable URL, resolving or refreshing as needed. */
  get(ref: MediaRef): Promise<string> {
    const entry = this.cache.get(refKey(ref));
    if (entry && !this.expiring(entry)) return Promise.resolve(entry.url);
    return this.load(ref, Boolean(entry));
  }

  /**
   * The element failed on `failedUrl`: fetch a new one. Concurrent failures share
   * one request; a URL that was already replaced is answered from the cache.
   */
  refresh(ref: MediaRef, failedUrl?: string): Promise<string> {
    const entry = this.cache.get(refKey(ref));
    if (entry && failedUrl && entry.url !== failedUrl && !this.expired(entry)) return Promise.resolve(entry.url);
    if (entry && entry.failures >= this.maxFailures) return Promise.reject(new MediaUrlError(ref));
    if (entry) entry.failures += 1;
    return this.load(ref, true);
  }

  /** The element played from the URL: its failure count starts over. */
  confirm(ref: MediaRef): void {
    const entry = this.cache.get(refKey(ref));
    if (entry) entry.failures = 0;
  }

  /** Warm the cache for refs the timeline will need. */
  prime(refs: readonly MediaRef[]): Promise<void> {
    return Promise.allSettled(refs.map((ref) => this.get(ref))).then(() => undefined);
  }

  clear(): void {
    this.cache.clear();
  }

  private expiring(entry: Entry): boolean {
    return entry.expiresAt !== null && this.now() >= entry.expiresAt - this.marginMs;
  }

  private expired(entry: Entry): boolean {
    return entry.expiresAt !== null && this.now() >= entry.expiresAt;
  }

  private load(ref: MediaRef, refresh: boolean): Promise<string> {
    const key = refKey(ref);
    const pending = this.inflight.get(key);
    if (pending) return pending;
    const request = this.resolver(ref, { refresh })
      .then((resolved) => {
        const { url, expiresAt } = typeof resolved === 'string' ? { url: resolved, expiresAt: undefined } : resolved;
        const failures = this.cache.get(key)?.failures ?? 0;
        this.cache.set(key, { url, expiresAt: expiresAt ?? expiryFromUrl(url), failures });
        return url;
      })
      .catch((error: unknown) => {
        throw error instanceof MediaUrlError ? error : new MediaUrlError(ref, error);
      })
      .finally(() => this.inflight.delete(key));
    this.inflight.set(key, request);
    return request;
  }
}
