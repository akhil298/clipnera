import { Skeleton, SkeletonGroup, SkeletonText } from '@/components/ui/Skeleton';

type Shape = 'page' | 'project' | 'editor' | 'table';

/** Route-segment skeletons from frontend.md §1.3. One live region each; shaped like the page that replaces them. */
export function SegmentLoading({ label, shape = 'page' }: { label: string; shape?: Shape }) {
  if (shape === 'editor') {
    return (
      <SkeletonGroup label={label} className="flex h-full flex-col gap-3 p-3">
        <Skeleton className="h-11 w-full" />
        <Skeleton className="min-h-0 flex-1" />
        <Skeleton className="h-40 w-full" />
      </SkeletonGroup>
    );
  }
  if (shape === 'table') {
    return (
      <SkeletonGroup label={label} className="flex flex-col gap-3 p-4 sm:p-6">
        <Skeleton className="h-8 w-48" />
        {Array.from({ length: 8 }, (_, row) => (
          <Skeleton key={row} className="h-10 w-full" />
        ))}
      </SkeletonGroup>
    );
  }
  return (
    <SkeletonGroup label={label} className="flex flex-col gap-6 p-4 sm:p-6">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-8 w-56" />
        <SkeletonText lines={1} className="w-72 max-w-full" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: shape === 'project' ? 6 : 3 }, (_, card) => (
          <Skeleton key={card} className="aspect-video w-full" />
        ))}
      </div>
    </SkeletonGroup>
  );
}
