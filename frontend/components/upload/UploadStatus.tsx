'use client';

import { UploadProgressItem } from '@/components/ui';
import { cancelUpload, dismissUpload, pauseUpload, resumeUpload } from '@/lib/upload/store';
import type { UploadTask } from '@/lib/upload/types';
import { uploadEta, uploadPercent, useRestoreUploads, useUploadFor, useUploads } from '@/lib/upload/useUploads';
import { formatBytes } from '@/lib/utils/videoFile';

// Registers the source-video kind, so uploads a reload interrupted can resume here.
import '@/lib/upload/sourceVideo';

/** One upload with pause, resume, retry and cancel wired to the shared uploader. */
export function UploadTaskItem({ task, className }: { task: UploadTask; className?: string }) {
  const meta = task.phase === 'uploading' || task.phase === 'paused' ? `${formatBytes(task.sentBytes)} of ${formatBytes(task.size)}` : formatBytes(task.size);
  return (
    <UploadProgressItem
      name={task.name}
      meta={meta}
      status={task.phase}
      percent={uploadPercent(task)}
      eta={uploadEta(task)}
      step={task.step ?? undefined}
      error={task.error ?? undefined}
      onPause={() => pauseUpload(task.id)}
      onResume={() => resumeUpload(task.id)}
      onRetry={() => resumeUpload(task.id)}
      onCancel={() => cancelUpload(task.id)}
      onDismiss={() => dismissUpload(task.id)}
      className={className}
    />
  );
}

/**
 * The upload feeding one project, for its progress page while the file is
 * still sending from this tab. Renders nothing once there is no upload.
 */
export function ProjectUploadStatus({ projectId, className }: { projectId: string; className?: string }) {
  useRestoreUploads();
  const task = useUploadFor(projectId);
  return task ? <UploadTaskItem task={task} className={className} /> : null;
}

/** Every upload in this tab, for the shell: a small fixed list in the corner while anything is uploading or needs a decision. */
export function UploadTray() {
  useRestoreUploads();
  const tasks = useUploads();
  if (tasks.length === 0) return null;
  return (
    <section
      aria-label="Uploads"
      className="fixed inset-x-4 bottom-20 z-cn-banner rounded-cn-lg border border-cn-border-strong bg-cn-surface-raised px-3 shadow-cn-2 md:inset-x-auto md:bottom-4 md:right-4 md:w-96"
    >
      <h2 className="pt-3 text-cn-label font-semibold text-cn-fg">Uploads</h2>
      <ul className="divide-y divide-cn-border">
        {tasks.map((task) => (
          <li key={task.id}>
            <UploadTaskItem task={task} />
          </li>
        ))}
      </ul>
    </section>
  );
}
