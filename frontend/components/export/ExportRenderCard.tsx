'use client';

import { useQuery } from '@tanstack/react-query';
import { CalendarClock, Check, Link2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

import { Button, RenderCard } from '@/components/ui';
import { getExportJob } from '@/lib/api/export/jobs';
import { useCopyToClipboard } from '@/lib/design/useCopyToClipboard';
import { useFlag } from '@/lib/flags/useFlag';
import { exportKeys } from '@/lib/query/keys/export';
import { downloadFile } from '@/lib/utils/clipExport';

import { fileName, isWorking } from './source';
import { cancelExport, type ExportJob, fromServerJob, retryExport, useExportStore } from './store';

const POLL_MS = 2000;

export interface ExportRenderCardProps {
  job: ExportJob;
  /** Amber Download when it is the view's one action (the editor); secondary elsewhere. */
  downloadPrimary?: boolean;
  className?: string;
}

/** The live card for one export (07 §6.6, editor §11.3). */
export function ExportRenderCard({ job, downloadPrimary = false, className }: ExportRenderCardProps) {
  useJobPolling(job);
  const router = useRouter();
  const canSchedule = useFlag('social_publishing');
  const { state: copyState, copy } = useCopyToClipboard();
  const link = job.shareUrl ?? job.url;

  const schedule = () => {
    const query = new URLSearchParams({
      project: job.projectId,
      ...(job.clipId ? { clip: job.clipId } : {}),
    });
    router.push(`/dashboard/scheduler?${query}`);
  };

  return (
    <RenderCard
      className={className}
      title={job.title}
      meta={job.meta}
      poster={job.poster}
      aspect={job.aspect}
      status={job.status}
      step={job.step}
      percent={job.percent}
      eta={job.eta}
      queuePosition={job.queuePosition}
      keepTabOpen={job.plan.kind === 'blocking'}
      error={job.error}
      facts={job.facts}
      downloadPrimary={downloadPrimary}
      onDownload={job.url ? () => downloadFile(job.url!, fileName(job.title, job.bundle ? 'zip' : 'mp4')) : undefined}
      actions={
        <>
          {link && (
            <Button size="sm" variant="ghost" leadingIcon={copyState === 'copied' ? <Check /> : <Link2 />} onClick={() => void copy(link)}>
              {copyState === 'copied' ? 'Link copied' : copyState === 'failed' ? 'Couldn’t copy' : 'Copy link'}
            </Button>
          )}
          {canSchedule && job.clipId && (
            <Button size="sm" variant="ghost" leadingIcon={<CalendarClock />} onClick={schedule}>
              Schedule
            </Button>
          )}
        </>
      }
      onCancel={() => void cancelExport(job.id)}
      onRetry={job.status === 'failed' && !job.retryable ? undefined : () => retryExport(job.id)}
    />
  );
}

/** NEEDS-BACKEND: EB-24 — polls the job until the events stream (EB-1, R-1) carries `job.*`. */
function useJobPolling(job: ExportJob) {
  const patch = useExportStore((state) => state.patch);
  const working = isWorking(job.status);
  const { data } = useQuery({
    queryKey: exportKeys.job(job.serverId ?? ''),
    queryFn: ({ signal }) => getExportJob(job.serverId!, signal),
    enabled: Boolean(job.serverId) && working,
    refetchInterval: POLL_MS,
  });
  useEffect(() => {
    if (data && working) patch(job.id, fromServerJob(data));
  }, [data, working, job.id, patch]);
}
