import React from 'react';
import { Skeleton } from './Skeleton';

export const FormSkeleton: React.FC = () => {
  return (
    <div className="space-y-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="space-y-1.5">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-9 w-full rounded-xl" />
        </div>
      ))}
      <Skeleton className="h-9 w-32 rounded-xl mt-2" />
    </div>
  );
};
