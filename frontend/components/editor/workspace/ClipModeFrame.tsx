'use client';

import { ChevronLeft, MonitorPlay, Rows3 } from 'lucide-react';
import Link from 'next/link';

import { TopBar } from '@/components/ui/TopBar';
import { cx, focusRing } from '@/lib/design/styles';

import { toolLabel } from './tools';
import { useArrangement } from './useArrangement';
import { useWorkspaceLayout } from './useWorkspaceLayout';
import { WorkspaceLayout } from './WorkspaceLayout';
import { ZoneNote } from './Zone';

export interface ClipModeFrameProps {
  projectId: string;
  clipId: string;
}

/**
 * The clip studio's frame (02-editor §12, E-D3): the same workspace in clip mode, with no
 * conversation until EB-14. CS1 replaces this file's zone bodies with the clip-doc wiring; the
 * layout, sizes (`storageKey: 'clip'`) and breakpoints come from `WorkspaceLayout`.
 */
export function ClipModeFrame({ projectId }: ClipModeFrameProps) {
  const layout = useWorkspaceLayout(useArrangement(), 'clip');
  const phone = layout.arrangement === 'phone';

  return (
    <WorkspaceLayout
      layout={layout}
      storageKey="clip"
      topBar={
        <TopBar
          variant="editor"
          start={
            <>
              <Link
                href={`/dashboard/projects/${encodeURIComponent(projectId)}`}
                aria-label="Back to clips"
                className={cx('inline-flex h-8 items-center gap-1 rounded-cn-sm px-1.5 text-cn-label font-semibold text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg', focusRing)}
              >
                <ChevronLeft aria-hidden className="size-4" />
                {!phone && <span aria-hidden>Clips</span>}
              </Link>
              <h1 className="truncate text-cn-label font-semibold text-cn-fg">Clip studio</h1>
            </>
          }
        />
      }
      renderPanel={() => <ZoneNote icon={<Rows3 />} title={toolLabel(layout.tool)} />}
      renderPreview={() => (
        <div data-theme="dark" className="flex min-h-0 flex-1">
          <ZoneNote icon={<MonitorPlay />} title="Clip preview" />
        </div>
      )}
      renderTimeline={() => <ZoneNote icon={<Rows3 />} title="Timeline" />}
    />
  );
}
