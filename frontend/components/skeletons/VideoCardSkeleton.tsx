import React from 'react';
import { Skeleton } from './Skeleton';

export const VideoCardSkeleton: React.FC = () => {
  return (
    <div className="group rounded-xl bg-neutral-900 border border-neutral-800 overflow-hidden shadow-md flex flex-col">
      <div className="relative aspect-[9/16] bg-neutral-950 overflow-hidden max-h-56">
        <Skeleton className="w-full h-full" />
      </div>
      <div className="p-3.5 flex-1 flex flex-col justify-between space-y-3">
        <div className="space-y-2">
          <Skeleton className="h-3.5 w-3/4" />
          <Skeleton className="h-2.5 w-full" />
          <Skeleton className="h-2.5 w-2/3" />
        </div>
        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-neutral-800/80">
          <Skeleton className="h-8 w-full rounded-lg" />
          <Skeleton className="h-8 w-full rounded-lg" />
        </div>
      </div>
    </div>
  );
};

export const VideoCardGridSkeleton: React.FC<{ count?: number }> = ({ count = 4 }) => {
  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <VideoCardSkeleton key={i} />
      ))}
    </div>
  );
};
