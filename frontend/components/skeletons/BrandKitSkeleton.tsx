import React from 'react';
import { Skeleton } from './Skeleton';

export const BrandKitSkeleton: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-neutral-900/90 border border-neutral-800 p-5 lg:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xl">
        <div className="space-y-2">
          <Skeleton className="h-3 w-32" />
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-3 w-64" />
        </div>
        <Skeleton className="h-10 w-40 rounded-xl" />
      </div>
      <div className="grid lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-7 space-y-5">
          {[1, 2, 3].map((i) => (
            <div key={i} className="p-5 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4 shadow-xl">
              <Skeleton className="h-4 w-40" />
              <div className="space-y-3">
                <Skeleton className="h-9 w-full rounded-xl" />
                <Skeleton className="h-9 w-full rounded-xl" />
              </div>
            </div>
          ))}
        </div>
        <div className="lg:col-span-5">
          <Skeleton className="aspect-[9/16] w-full rounded-[36px]" />
        </div>
      </div>
    </div>
  );
};
