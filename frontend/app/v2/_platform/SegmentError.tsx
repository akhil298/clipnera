'use client';

import { RotateCcw, TriangleAlert } from 'lucide-react';

import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';

export interface SegmentErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
  /** Which segment failed, e.g. "dashboard". */
  segment: string;
}

/** The body of every v2 `error.tsx`: what happened, one way forward, and an id support can look up. */
export function SegmentError({ error, reset, segment }: SegmentErrorProps) {
  return (
    <section className="flex flex-1 items-center justify-center px-4 py-12" data-segment={segment}>
      <EmptyState
        icon={<TriangleAlert />}
        title="This part of Clipnera didn't load"
        description="Your work is safe. Try again, and if it keeps happening, send us the report id below."
        action={
          <Button leadingIcon={<RotateCcw />} onClick={reset}>
            Try again
          </Button>
        }
        secondaryAction={
          error.digest ? <span className="font-cn-mono text-cn-label text-cn-fg-muted">Report id {error.digest}</span> : null
        }
      />
    </section>
  );
}
