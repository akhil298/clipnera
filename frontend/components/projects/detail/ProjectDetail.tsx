'use client';

import { RotateCcw, TriangleAlert } from 'lucide-react';
import { notFound } from 'next/navigation';

import { InlineAlert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { WorkingText } from '@/components/ui/WorkingText';
import { isForbidden, isNotFound } from '@/lib/api/errors';
import { stepWords } from '@/lib/projects/run';

import { ClipsSection } from './ClipsSection';
import { ProjectHeader } from './ProjectHeader';
import { ProjectSkeleton } from './ProjectSkeleton';
import { RunOutcome } from './RunOutcome';
import { RunProgress } from './RunProgress';
import { type Phase, stagesOf } from './run';
import { useProjectRun } from './useProjectRun';

function statusWord(phase: Phase, run: ReturnType<typeof useProjectRun>): string | undefined {
  if (phase === 'done') {
    const count = run.clips.data?.clips.length;
    return count === undefined ? undefined : `${count} clip${count === 1 ? '' : 's'} ready`;
  }
  if (phase !== 'running') return undefined;
  const running = run.steps.find((log) => log.status === 'running');
  return running ? stepWords(running.step) : stagesOf(phase, run.steps).find((stage) => stage.status === 'active')?.label;
}

/**
 * `/dashboard/projects/[projectId]`: live progress while clips are being
 * made, the clips once they are ready, and the way back from a failed or
 * stopped run. The same URL throughout, so links never break (screens/01 §10).
 */
export function ProjectDetail({ projectId }: { projectId: string }) {
  const run = useProjectRun(projectId);
  const { project, phase } = run;

  if (project.isPending) return <ProjectSkeleton />;
  if (project.isError) {
    if (isNotFound(project.error) || isForbidden(project.error)) notFound();
    return (
      <section className="flex flex-1 items-center justify-center px-4 py-12">
        <EmptyState
          icon={<TriangleAlert />}
          title="This project didn’t load"
          description="I couldn’t reach Clipnera just now. Nothing was lost, and work already running carries on."
          action={
            <Button leadingIcon={<RotateCcw />} loading={project.isFetching} loadingLabel="Trying again" onClick={() => void project.refetch()}>
              Try again
            </Button>
          }
        />
      </section>
    );
  }
  // Wait for the run's own status so a started run never flashes as "not started".
  if (!phase || (run.status.isPending && project.data.status !== 'pending')) return <ProjectSkeleton />;

  const data = project.data;
  const live = phase === 'importing' || phase === 'running';
  const clips = run.clips.data?.clips;
  const showClips = phase === 'done' || Boolean(clips?.length) || (live && run.clips.isFetched);

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      {run.reconnecting && (
        <InlineAlert tone="info" live="status">
          <WorkingText>Reconnecting.</WorkingText> Your clips are still being made; this page catches up when the connection is back.
        </InlineAlert>
      )}

      <ProjectHeader project={data} phase={phase} statusWord={statusWord(phase, run)} credits={run.credits.data} />

      {phase !== 'importing' && phase !== 'running' && (
        <div className="max-w-3xl">
          <RunOutcome
            phase={phase}
            title={data.title}
            steps={run.steps}
            clips={clips}
            sourceSeconds={data.duration_seconds}
            credits={run.credits.data}
            onRetry={run.retry}
            retrying={run.retrying}
            retryError={run.retryError}
            onStart={run.start}
            starting={run.starting}
            startError={run.startError}
          />
        </div>
      )}

      {(live || ((phase === 'failed' || phase === 'stopped') && run.steps.length > 0)) && (
        <div className="max-w-3xl">
          <RunProgress
            phase={phase}
            steps={run.steps}
            sourceType={data.source_type}
            sourceSeconds={data.duration_seconds}
            download={run.download.data}
            clipsSoFar={clips?.length}
            onStop={() => run.cancel.mutate()}
            stopping={run.cancel.isPending}
            onRetryStep={phase === 'failed' && !run.retrying ? run.retry : undefined}
          />
          {run.cancel.isError && (
            <InlineAlert tone="danger" live="alert" className="mt-3">
              I couldn’t stop it just now. It’s still running; try Stop again.
            </InlineAlert>
          )}
        </div>
      )}

      {run.clips.isError && !clips ? (
        <InlineAlert
          tone="danger"
          action={
            <Button size="sm" variant="secondary" loading={run.clips.isFetching} onClick={() => void run.clips.refetch()}>
              Try again
            </Button>
          }
        >
          I couldn’t load the clips. They’re safe; this is only the list.
        </InlineAlert>
      ) : (
        showClips && <ClipsSection clips={clips ?? []} loading={run.clips.isPending} streaming={live} sourceSeconds={data.duration_seconds} />
      )}
    </div>
  );
}
