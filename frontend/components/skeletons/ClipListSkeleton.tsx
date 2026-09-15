import React from 'react';
import { Skeleton } from './Skeleton';

export const ClipListSkeleton: React.FC = () => {
  return (
    <div className="space-y-3.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="rounded-xl p-4 lg:p-5 border border-neutral-800 bg-neutral-900/60">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <Skeleton className="w-13 h-13 rounded-xl shrink-0" />
              <div className="space-y-2">
                <Skeleton className="h-3.5 w-24" />
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-3 w-20" />
              </div>
            </div>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <Skeleton className="h-8 w-20 rounded-lg" />
              <Skeleton className="h-8 w-8 rounded-lg" />
            </div>
          </div>
          <div className="mt-3.5 p-2.5 rounded-lg bg-neutral-950 border border-neutral-800/80">
            <Skeleton className="h-3 w-full" />
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs pt-2 border-t border-neutral-800/60">
            <Skeleton className="h-2.5 w-48" />
            <div className="flex items-center gap-3">
              <Skeleton className="h-2.5 w-16" />
              <Skeleton className="h-2.5 w-16" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
