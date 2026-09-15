import React from 'react';
import { Skeleton } from './Skeleton';

export const TableRowSkeleton: React.FC = () => {
  return (
    <div className="flex items-center gap-4 py-3 px-4">
      <Skeleton className="w-8 h-8 rounded-full shrink-0" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3.5 w-48" />
        <Skeleton className="h-2.5 w-32" />
      </div>
      <Skeleton className="h-8 w-20 rounded-lg shrink-0" />
      <Skeleton className="h-8 w-8 rounded-lg shrink-0" />
    </div>
  );
};

export const TableSkeleton: React.FC<{ rows?: number }> = ({ rows = 5 }) => {
  return (
    <div className="rounded-xl bg-neutral-900/80 border border-neutral-800 overflow-hidden">
      <div className="flex items-center gap-4 py-3 px-4 border-b border-neutral-800">
        <Skeleton className="h-3.5 w-24" />
        <Skeleton className="h-3.5 w-32" />
        <Skeleton className="h-3.5 w-20 ml-auto" />
        <Skeleton className="h-3.5 w-8" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <TableRowSkeleton key={i} />
      ))}
    </div>
  );
};
