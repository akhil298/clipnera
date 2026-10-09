'use client';

import { useMemo } from 'react';

import { cx } from '@/lib/design/styles';

import { ExportRenderCard } from './ExportRenderCard';
import { type ExportJob, useExportStore } from './store';

/** This session's exports of a project, newest first. */
export function useExportJobs(projectId: string | undefined): ExportJob[] {
  const jobs = useExportStore((state) => state.jobs);
  return useMemo(() => (projectId ? jobs.filter((job) => job.projectId === projectId) : []), [jobs, projectId]);
}

export interface ExportJobsProps {
  projectId: string;
  downloadPrimary?: boolean;
  className?: string;
}

/** Render cards for a project (the Project page, the editor's pinned "Exports" row). Renders nothing until an export starts. */
export function ExportJobs({ projectId, downloadPrimary, className }: ExportJobsProps) {
  const jobs = useExportJobs(projectId);
  if (jobs.length === 0) return null;
  return (
    <section aria-label="Exports" className={cx('flex flex-col gap-2', className)}>
      {jobs.map((job) => (
        <ExportRenderCard key={job.id} job={job} downloadPrimary={downloadPrimary} />
      ))}
    </section>
  );
}
