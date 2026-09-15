import React from 'react';
import { Skeleton } from './Skeleton';

export const HeaderSkeleton: React.FC = () => {
  return (
    <header className="sticky top-0 z-20 h-16 w-full shrink-0 border-b border-neutral-800/80 bg-neutral-950/90 backdrop-blur-md px-4 lg:px-6 flex items-center justify-between gap-3">
      <div className="flex items-center gap-3 min-w-0">
        <Skeleton className="w-9 h-9 rounded-xl lg:hidden" />
        <div className="flex items-center gap-2">
          <Skeleton className="h-4 w-16 hidden sm:block" />
          <Skeleton className="h-3 w-4 hidden sm:block" />
          <Skeleton className="h-5 w-32" />
        </div>
      </div>
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        <Skeleton className="h-9 w-28 rounded-xl hidden md:flex" />
        <Skeleton className="h-9 w-20 rounded-xl" />
        <Skeleton className="h-9 w-9 rounded-xl" />
        <Skeleton className="h-9 w-9 rounded-xl" />
        <Skeleton className="h-9 w-9 rounded-xl" />
      </div>
    </header>
  );
};
