'use client';

import { RotateCcw, TriangleAlert } from 'lucide-react';

import type { SegmentErrorProps } from '@/app/v2/_platform/SegmentError';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';

/**
 * The editor crashed. Unsent edits are already in IndexedDB (the doc store saves every pending
 * batch), so a full reload restores and sends them; nothing here needs to save first.
 */
export default function EditorError({ error }: Omit<SegmentErrorProps, 'segment'>) {
  return (
    <section className="flex flex-1 items-center justify-center px-4 py-12" data-segment="editor">
      <EmptyState
        icon={<TriangleAlert />}
        title="The editor stopped working"
        description="Edits you haven't sent yet are kept on this device and go through when the editor reopens."
        action={
          <Button leadingIcon={<RotateCcw />} onClick={() => window.location.reload()}>
            Reload editor
          </Button>
        }
        secondaryAction={error.digest ? <span className="font-cn-mono text-cn-label text-cn-fg-muted">Report id {error.digest}</span> : null}
      />
    </section>
  );
}
