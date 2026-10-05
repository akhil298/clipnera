/**
 * The resumable uploader's contract. One engine sends any file to S3 in
 * presigned parts; a `UploadKind` says which endpoints start, finish and
 * abort a multipart upload for one purpose (source video, B-roll, …) and
 * what the server does with the file afterwards.
 */

/** Where the parts go: one presigned PUT URL per part, in order. */
export interface PartPlan {
  uploadId: string;
  partSize: number;
  partUrls: string[];
}

/** S3's receipt for one part; `complete` sends them back. */
export interface UploadedPart {
  part_number: number;
  etag: string;
}

/** A multipart upload the server has opened. `id` is the server resource it belongs to (a project id for a source video). */
export interface UploadTarget {
  id: string;
  plan: PartPlan;
}

/** What comes after the bytes land, while this tab is still needed (shown as `step`). */
export interface UploadAfterStep<M> {
  step: string;
  run: (target: UploadTarget, meta: M, signal: AbortSignal) => Promise<void>;
}

export interface UploadKind<M> {
  /** Stable name; persisted uploads find their kind again by it after a reload. */
  kind: string;
  begin: (file: File, meta: M) => Promise<UploadTarget>;
  complete: (target: UploadTarget, parts: UploadedPart[], meta: M) => Promise<void>;
  abort: (target: UploadTarget) => Promise<void>;
  after?: UploadAfterStep<M>;
}

/** Same words as `UploadProgressItem`'s status. */
export type UploadPhase = 'queued' | 'uploading' | 'paused' | 'processing' | 'done' | 'failed';

/** One upload as the UI sees it. Serializable; the File itself lives in the runtime and IndexedDB. */
export interface UploadTask {
  id: string;
  kind: string;
  name: string;
  size: number;
  sentBytes: number;
  phase: UploadPhase;
  /** Measured while bytes flow; null when paused or unknown. */
  bytesPerSecond: number | null;
  /** The step shown while `processing`. */
  step: string | null;
  error: string | null;
  /** The server resource, once `begin` has answered. */
  targetId: string | null;
  meta: unknown;
}
