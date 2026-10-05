import { Hammer } from 'lucide-react';

import { EmptyState } from '@/components/ui/EmptyState';

/** Stand-in for a v2 route until its area builds it, so every URL resolves from day one. Replace the page, not this. */
export function Placeholder({ route, area }: { route: string; area: string }) {
  return (
    <section className="flex flex-1 items-center justify-center px-4 py-12">
      <EmptyState
        icon={<Hammer />}
        title="Coming in Wave 6"
        description={
          <>
            <span className="font-cn-mono text-cn-fg">{route}</span>
            <span className="block">{area}</span>
          </>
        }
      />
    </section>
  );
}
