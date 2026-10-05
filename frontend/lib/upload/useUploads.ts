'use client';

import { useEffect } from 'react';
import { useShallow } from 'zustand/react/shallow';

import { restoreUploads, useUploadStore } from './store';
import type { UploadTask } from './types';

/** Every upload of one kind (all kinds when omitted), oldest first. */
export function useUploads(kind?: string): UploadTask[] {
  return useUploadStore(useShallow((state) => Object.values(state.tasks).filter((task) => !kind || task.kind === kind)));
}

/** The upload feeding one server resource, e.g. a project's source video. */
export function useUploadFor(targetId: string): UploadTask | undefined {
  return useUploadStore((state) => Object.values(state.tasks).find((task) => task.targetId === targetId));
}

/** Brings back uploads a reload interrupted. Mount it wherever uploads are listed. */
export function useRestoreUploads(): void {
  useEffect(() => {
    void restoreUploads();
  }, []);
}

/** 0–100. */
export const uploadPercent = (task: UploadTask): number => (task.size > 0 ? (task.sentBytes / task.size) * 100 : 0);

/** "About 3 min left", or undefined until there is a measured rate. */
export function uploadEta(task: UploadTask): string | undefined {
  if (task.phase !== 'uploading' || !task.bytesPerSecond) return undefined;
  const seconds = (task.size - task.sentBytes) / task.bytesPerSecond;
  if (!Number.isFinite(seconds)) return undefined;
  if (seconds < 60) return 'Less than a minute left';
  const minutes = Math.round(seconds / 60);
  return minutes < 60 ? `About ${minutes} min left` : `About ${Math.floor(minutes / 60)} h ${minutes % 60} min left`;
}
