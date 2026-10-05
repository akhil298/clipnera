'use client';

import { RotateCcw, TriangleAlert } from 'lucide-react';

import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';

/** In-shell error for the project page: what happened, what is safe, one action (screens/01 §6). */
export default function ProjectError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <section className="flex flex-1 items-center justify-center px-4 py-12" data-segment="project">
      <EmptyState
        icon={<TriangleAlert />}
        title="This project didn’t load"
        description="Nothing was lost, and work already running carries on. Try again, and if it keeps happening, send support the report id below."
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
