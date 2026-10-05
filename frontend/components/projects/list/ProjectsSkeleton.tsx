import { Skeleton, SkeletonGroup } from '@/components/ui';

export const GRID_CLASS = 'grid grid-cols-1 gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-3 xl:grid-cols-4 xl:gap-6';

/** Six placeholder tiles in one live region (screens/01 §8, loading). */
export function ProjectsSkeleton() {
  return (
    <SkeletonGroup label="Loading projects" className={GRID_CLASS}>
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="flex flex-col gap-2">
          <Skeleton className="aspect-video w-full rounded-cn-lg" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      ))}
    </SkeletonGroup>
  );
}
