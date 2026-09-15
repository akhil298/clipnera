import React from 'react';
import { Skeleton } from './Skeleton';

export const ProfileSkeleton: React.FC = () => {
  return (
    <div className="max-w-2xl p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-6 shadow-xl">
      <div className="flex items-center gap-4 pb-4 border-b border-neutral-800">
        <Skeleton className="w-16 h-16 rounded-xl" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-3 w-48" />
          <Skeleton className="h-5 w-24 rounded-full" />
        </div>
      </div>
      <div className="space-y-4">
        <div className="space-y-1.5">
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-9 w-full rounded-xl" />
        </div>
        <div className="space-y-1.5">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-9 w-full rounded-xl" />
        </div>
      </div>
    </div>
  );
};
