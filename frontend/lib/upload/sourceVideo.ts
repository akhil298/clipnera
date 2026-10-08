import { apiFetch } from '@/lib/api/client';
import type { PipelineStartRequest } from '@/lib/api/pipeline';

import { defineUploadKind } from './store';
import type { UploadedPart } from './types';

/** backend/uploads/schema.py, field for field. Routes return the `{data, message, error}` envelope. */
export const VIDEO_CONTENT_TYPES = ['video/mp4', 'video/quicktime', 'video/webm', 'video/x-matroska'] as const;
export type VideoContentType = (typeof VIDEO_CONTENT_TYPES)[number];

export interface VideoUploadInitRequest {
  filename: string;
  content_type: VideoContentType;
  size_bytes: number;
  duration_seconds: number | null;
}

export interface VideoUploadInitResponse {
  project_id: string;
  upload_id: string;
  part_size: number;
  part_urls: string[];
}

export interface VideoUploadCompleteRequest {
  upload_id: string;
  parts: UploadedPart[];
  /** Started by the server once the upload is ready (charged then, refunded if it can't start). */
  pipeline?: PipelineStartRequest | null;
}

export interface VideoUploadCompleteResponse {
  project_id: string;
  status: string;
}

export interface VideoUploadAbortRequest {
  upload_id: string;
}

const initVideoUpload = (body: VideoUploadInitRequest) =>
  apiFetch<VideoUploadInitResponse>('/uploads/video/init', { method: 'POST', body, timeoutMs: 30_000 });

const completeVideoUpload = (projectId: string, body: VideoUploadCompleteRequest) =>
  apiFetch<VideoUploadCompleteResponse>(`/uploads/video/${encodeURIComponent(projectId)}/complete`, { method: 'POST', body, timeoutMs: 60_000 });

const abortVideoUpload = (projectId: string, body: VideoUploadAbortRequest) =>
  apiFetch<null>(`/uploads/video/${encodeURIComponent(projectId)}/abort`, { method: 'POST', body });

export const isVideoContentType = (type: string): type is VideoContentType => (VIDEO_CONTENT_TYPES as readonly string[]).includes(type);

export interface SourceVideoMeta {
  /** From the file's own metadata, so the server refuses an over-long video before any bytes move. */
  durationSeconds: number | null;
  /** The clip run the server starts once the video is in. */
  run: PipelineStartRequest;
}

/**
 * A project's source video: `begin` creates the project, the bytes go straight
 * to S3, and `complete` hands the run to the server, which starts it once it
 * has read the file. The tab is needed only until `complete` answers.
 */
export const sourceVideoUpload = defineUploadKind<SourceVideoMeta>({
  kind: 'source_video',
  begin: async (file, meta) => {
    if (!isVideoContentType(file.type)) throw new Error('Use an MP4, MOV, WebM or MKV video.');
    const init = await initVideoUpload({
      filename: file.name,
      content_type: file.type,
      size_bytes: file.size,
      duration_seconds: meta.durationSeconds,
    });
    return { id: init.project_id, plan: { uploadId: init.upload_id, partSize: init.part_size, partUrls: init.part_urls } };
  },
  complete: async (target, parts, meta) => {
    await completeVideoUpload(target.id, { upload_id: target.plan.uploadId, parts, pipeline: meta.run });
  },
  abort: async (target) => {
    await abortVideoUpload(target.id, { upload_id: target.plan.uploadId });
  },
});
