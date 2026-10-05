'use client';

import Link from 'next/link';

import { Card, ProgressBar, WorkingText, cardLinkOverlay } from '@/components/ui';
import { cx } from '@/lib/design/styles';

import { projectHref } from './projectState';
import type { ProjectWithRun } from './useHomeData';

/** Running projects, each linking to its progress page. Rendered only while something runs. */
export function InProgressRow({ items }: { items: readonly ProjectWithRun[] }) {
  const running = items.filter((item) => item.run.kind === 'running');
  if (running.length === 0) return null;

  return (
    <section aria-labelledby="home-in-progress" className="flex flex-col gap-3">
      <h2 id="home-in-progress" className="text-cn-title-sm font-semibold text-cn-fg">
        In progress
      </h2>
      <ul className="grid gap-3 md:grid-cols-2">
        {running.map(({ project, run }) =>
          run.kind === 'running' ? (
            <li key={project.id}>
              <Card interactive className="flex flex-col gap-2">
                <Link href={projectHref(project.id)} className={cx(cardLinkOverlay, 'truncate text-cn-body font-semibold text-cn-fg')}>
                  {project.title}
                </Link>
                <WorkingText className="text-cn-label">
                  {run.step}
                  {run.total > 0 && ` · step ${Math.min(run.done + 1, run.total)} of ${run.total}`}
                </WorkingText>
                <ProgressBar
                  label={`${project.title} progress`}
                  value={run.total > 0 ? run.done : undefined}
                  max={run.total || undefined}
                  valueText={run.total > 0 ? `${run.done} of ${run.total} steps done` : undefined}
                  hideLabel
                  size="sm"
                />
              </Card>
            </li>
          ) : null,
        )}
      </ul>
    </section>
  );
}
