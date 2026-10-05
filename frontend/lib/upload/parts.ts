import type { PartPlan, UploadedPart } from './types';

const CONCURRENCY = 4;
const ATTEMPTS = 3;

/** A presigned part URL past its lifetime (S3 answers 403): only a new upload helps. */
export class PartUrlExpiredError extends Error {
  constructor() {
    super('The upload link expired.');
    this.name = 'PartUrlExpiredError';
  }
}

const abortError = () => new DOMException('Upload paused', 'AbortError');

/** PUTs one part and resolves its ETag; `onBytes` reports bytes sent so far for this part. */
function putPart(url: string, body: Blob, onBytes: (sent: number) => void, signal: AbortSignal): Promise<string> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(abortError());
    const xhr = new XMLHttpRequest();
    const onAbort = () => xhr.abort();
    xhr.open('PUT', url);
    xhr.upload.onprogress = (event) => onBytes(event.loaded);
    xhr.onload = () => {
      signal.removeEventListener('abort', onAbort);
      // The bucket's CORS must expose ETag for this to be readable.
      const etag = xhr.getResponseHeader('ETag');
      if (xhr.status >= 200 && xhr.status < 300 && etag) resolve(etag);
      else if (xhr.status === 403) reject(new PartUrlExpiredError());
      else reject(new Error(`Part upload failed (${xhr.status})`));
    };
    xhr.onerror = () => {
      signal.removeEventListener('abort', onAbort);
      reject(new Error('The connection dropped during the upload.'));
    };
    xhr.onabort = () => reject(abortError());
    signal.addEventListener('abort', onAbort, { once: true });
    xhr.send(body);
  });
}

function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener('abort', () => {
      clearTimeout(timer);
      reject(abortError());
    }, { once: true });
  });
}

async function putWithRetry(url: string, body: Blob, onBytes: (sent: number) => void, signal: AbortSignal): Promise<string> {
  for (let attempt = 1; ; attempt += 1) {
    try {
      return await putPart(url, body, onBytes, signal);
    } catch (err) {
      onBytes(0);
      if (signal.aborted || err instanceof PartUrlExpiredError || attempt >= ATTEMPTS) throw err;
      await wait(1000 * 2 ** (attempt - 1), signal);
    }
  }
}

export interface SendPartsOptions {
  file: Blob;
  plan: PartPlan;
  /** Parts already in S3 (part number → ETag); skipped, and filled in as parts finish. */
  done: Map<number, string>;
  signal: AbortSignal;
  /** Total bytes in S3 or in flight. */
  onProgress: (sentBytes: number) => void;
  onPartDone?: (part: UploadedPart) => void;
}

/** Sends every missing part, four at a time, each retried with backoff. Aborting the signal pauses; call again to resume. */
export async function sendParts({ file, plan, done, signal, onProgress, onPartDone }: SendPartsOptions): Promise<UploadedPart[]> {
  const total = plan.partUrls.length;
  const partBytes = (index: number) => Math.min(plan.partSize, file.size - index * plan.partSize);
  const inFlight = new Map<number, number>();
  const report = () => {
    let sent = 0;
    done.forEach((_, number) => (sent += partBytes(number - 1)));
    inFlight.forEach((bytes) => (sent += bytes));
    onProgress(Math.min(sent, file.size));
  };
  const queue = Array.from({ length: total }, (_, index) => index).filter((index) => !done.has(index + 1));
  report();

  // One failed part stops the others, so nothing keeps sending after the caller has given up.
  const local = new AbortController();
  const stop = () => local.abort();
  signal.addEventListener('abort', stop, { once: true });

  const worker = async () => {
    for (let index = queue.shift(); index !== undefined; index = queue.shift()) {
      const start = index * plan.partSize;
      const etag = await putWithRetry(
        plan.partUrls[index],
        file.slice(start, start + partBytes(index)),
        (bytes) => {
          inFlight.set(index, bytes);
          report();
        },
        local.signal,
      );
      inFlight.delete(index);
      done.set(index + 1, etag);
      onPartDone?.({ part_number: index + 1, etag });
      report();
    }
  };

  const guarded = () => worker().catch((err: unknown) => {
    stop();
    throw err;
  });
  try {
    await Promise.all(Array.from({ length: Math.min(CONCURRENCY, queue.length) }, guarded));
  } finally {
    signal.removeEventListener('abort', stop);
  }
  return [...done].map(([part_number, etag]) => ({ part_number, etag })).sort((a, b) => a.part_number - b.part_number);
}
