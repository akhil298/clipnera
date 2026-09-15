import React from 'react';
import { Skeleton } from './Skeleton';

export const SidebarSkeleton: React.FC = () => {
  return (
    <aside className="hidden lg:flex flex-col shrink-0 border-r border-neutral-800/80 h-screen sticky top-0 w-64 bg-neutral-950">
      <div className="p-4 space-y-4">
        <div className="flex items-center gap-2.5">
          <Skeleton className="w-9 h-9 rounded-xl shrink-0" />
          <div className="space-y-1.5 flex-1">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-3 w-16" />
          </div>
        </div>
        <Skeleton className="h-9 w-full rounded-xl" />
        <Skeleton className="h-9 w-full rounded-xl" />
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-2 pb-6 space-y-6">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-3 w-20 mx-3" />
            <Skeleton className="h-8 w-full rounded-xl" />
            <Skeleton className="h-8 w-full rounded-xl" />
          </div>
        ))}
      </div>
      <div className="p-3 border-t border-neutral-900 space-y-3">
        <Skeleton className="h-16 w-full rounded-xl" />
        <div className="flex items-center gap-2.5 p-2">
          <Skeleton className="w-8 h-8 rounded-lg shrink-0" />
          <div className="space-y-1.5 flex-1">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-2.5 w-28" />
          </div>
        </div>
      </div>
    </aside>
  );
};
