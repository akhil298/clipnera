import { apiFetch } from '@/lib/api/client';
import { startClipRunWhenReady, type ClipRunRequest } from '@/lib/api/pipeline';

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
  /** The clip run to start once the video is in. */
  run: ClipRunRequest;
}

/**
 * A project's source video: `begin` creates the project, the bytes go straight
 * to S3, and once the server has read the file the clip run starts.
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
  complete: async (target, parts) => {
    await completeVideoUpload(target.id, { upload_id: target.plan.uploadId, parts });
  },
  abort: async (target) => {
    await abortVideoUpload(target.id, { upload_id: target.plan.uploadId });
  },
  after: {
    step: 'Getting your video ready',
    run: async (target, meta, signal) => {
      await startClipRunWhenReady(target.id, meta.run, signal);
    },
  },
});
