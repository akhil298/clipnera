import React from 'react';
import { SidebarSkeleton } from './SidebarSkeleton';
import { HeaderSkeleton } from './HeaderSkeleton';
import { StatsSkeleton } from './StatsSkeleton';
import { ProjectCardGridSkeleton } from './ProjectCardSkeleton';
import { Skeleton } from './Skeleton';

export const DashboardSkeleton: React.FC = () => {
  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex font-['Plus_Jakarta_Sans',sans-serif]">
      <SidebarSkeleton />
      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-y-auto">
        <HeaderSkeleton />
        <main className="flex-1 min-h-0 w-full p-4 sm:p-6 lg:p-8 space-y-8">
          <div className="relative overflow-hidden rounded-2xl bg-neutral-900/90 border border-neutral-800 p-6 lg:p-8 shadow-xl space-y-4">
            <div className="space-y-2">
              <Skeleton className="h-3 w-40" />
              <Skeleton className="h-6 w-full max-w-sm" />
              <Skeleton className="h-4 w-full max-w-xl" />
            </div>
            <Skeleton className="h-10 w-full max-w-xl rounded-xl" />
          </div>
          <StatsSkeleton />
          <div className="space-y-3.5">
            <Skeleton className="h-5 w-48" />
            <ProjectCardGridSkeleton count={6} />
          </div>
        </main>
      </div>
    </div>
  );
};
