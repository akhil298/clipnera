'use client';

import { Download, Film, FileText, GitCommitVertical, Image as ImageIcon } from 'lucide-react';
import type { ReactNode } from 'react';

import { buttonClasses } from '@/components/ui';
import type { RunOutput } from '@/lib/api/editor/types';
import { cx } from '@/lib/design/styles';

export interface OutputsRowProps {
  /** `run.result.outputs` (EB-21). */
  outputs: ReadonlyArray<RunOutput>;
  /** Renders a `render` output as a live RenderCard (X2, through the RenderCardSlot request R-2). */
  renderOutput?: (output: RunOutput) => ReactNode;
  /** Opens a `version` output in the versions drawer. */
  onOpenVersion?: (versionId: string) => void;
  className?: string;
}

const ICON: Record<RunOutput['kind'], ReactNode> = {
  version: <GitCommitVertical />,
  render: <Film />,
  caption_file: <FileText />,
  thumbnail: <ImageIcon />,
};

/** What a turn produced (Perplexity Labs' Assets): versions, renders, caption files, thumbnails. Hidden when empty. */
export function OutputsRow({ outputs, renderOutput, onOpenVersion, className }: OutputsRowProps) {
  if (outputs.length === 0) return null;
  const renders = renderOutput ? outputs.filter((output) => output.kind === 'render') : [];
  const files = outputs.filter((output) => !renders.includes(output));
  return (
    <section aria-label="Outputs" className={cx('flex flex-col gap-2', className)}>
      <p className="text-cn-caption font-semibold text-cn-fg-muted">Outputs</p>
      {files.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {files.map((output) => (
            <li key={`${output.kind}:${output.id}`}>
              <OutputItem output={output} onOpenVersion={onOpenVersion} />
            </li>
          ))}
        </ul>
      )}
      {renders.map((output) => (
        <div key={output.id}>{renderOutput?.(output)}</div>
      ))}
    </section>
  );
}

function OutputItem({ output, onOpenVersion }: { output: RunOutput; onOpenVersion?: (id: string) => void }) {
  const classes = cx(buttonClasses({ variant: 'secondary', size: 'sm' }), 'max-w-full');
  const body = (
    <>
      <span aria-hidden className="inline-flex text-cn-fg-muted [&_svg]:size-3.5">
        {ICON[output.kind]}
      </span>
      <span className="truncate">{output.label}</span>
    </>
  );
  if (output.url) {
    return (
      <a href={output.url} download className={classes} aria-label={`Download ${output.label}`}>
        {body}
        <Download aria-hidden className="size-3.5 text-cn-fg-muted" />
      </a>
    );
  }
  if (output.kind === 'version' && onOpenVersion) {
    return (
      <button type="button" onClick={() => onOpenVersion(output.id)} className={classes}>
        {body}
      </button>
    );
  }
  return <span className="inline-flex h-8 items-center gap-1.5 px-1 text-cn-label text-cn-fg-secondary">{body}</span>;
}
