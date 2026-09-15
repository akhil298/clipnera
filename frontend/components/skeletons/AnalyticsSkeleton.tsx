import React from 'react';
import { Skeleton } from './Skeleton';

export const AnalyticsSkeleton: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-neutral-900/90 border border-neutral-800 p-5 lg:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xl">
        <div className="space-y-2">
          <Skeleton className="h-3 w-32" />
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-3 w-64" />
        </div>
        <Skeleton className="h-16 w-32 rounded-xl" />
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="p-4 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-2">
            <div className="flex items-center justify-between">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="w-4 h-4 rounded" />
            </div>
            <Skeleton className="h-7 w-20" />
            <Skeleton className="h-2.5 w-32" />
          </div>
        ))}
      </div>
      <div className="p-5 lg:p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4 shadow-xl">
        <Skeleton className="h-4 w-64" />
        <Skeleton className="h-72 w-full" />
      </div>
      <div className="grid lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-6 p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4 shadow-xl">
          <Skeleton className="h-4 w-48" />
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="p-3.5 rounded-xl bg-neutral-950 border border-neutral-800 space-y-2">
              <div className="flex items-center justify-between">
                <Skeleton className="h-3.5 w-24" />
                <Skeleton className="h-3.5 w-20" />
              </div>
              <Skeleton className="h-1.5 w-full rounded-full" />
            </div>
          ))}
        </div>
        <div className="lg:col-span-6 p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4 shadow-xl">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-32 w-full rounded-xl" />
        </div>
      </div>
    </div>
  );
};
