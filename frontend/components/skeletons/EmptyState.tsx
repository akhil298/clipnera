import React from 'react';
import { Skeleton } from './Skeleton';

export const EmptyState: React.FC<{ icon?: React.ReactNode; title?: string; description?: string }> = ({
  icon,
  title = 'No items found',
  description = 'There are no items to display at this time.',
}) => {
  return (
    <div className="p-8 text-center rounded-2xl bg-neutral-900/40 border border-neutral-800/80 space-y-3">
      {icon || <Skeleton className="w-10 h-10 rounded-full mx-auto" />}
      <h3 className="text-sm font-bold text-neutral-300">{title}</h3>
      <p className="text-xs text-neutral-500 max-w-sm mx-auto">{description}</p>
    </div>
  );
};
