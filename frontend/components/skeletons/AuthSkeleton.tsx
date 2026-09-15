import React from 'react';
import { Skeleton } from './Skeleton';

export const AuthSkeleton: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-neutral-950 text-neutral-100 font-['Plus_Jakarta_Sans',sans-serif] px-4">
      <div className="w-full max-w-md">
        <div className="w-full rounded-2xl bg-neutral-900/90 border border-neutral-800 p-6 shadow-xl space-y-6">
          <div className="text-center space-y-2">
            <Skeleton className="h-6 w-40 mx-auto" />
            <Skeleton className="h-3 w-56 mx-auto" />
          </div>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-9 w-full rounded-xl" />
            </div>
            <div className="space-y-1.5">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-9 w-full rounded-xl" />
            </div>
            <Skeleton className="h-9 w-full rounded-xl mt-2" />
          </div>
        </div>
      </div>
    </div>
  );
};
