import { Skeleton, SkeletonGroup, SkeletonText } from '@/components/ui/Skeleton';
import { ASPECT_CLASS } from '@/components/ui/VideoThumb';

/** Shaped like the project page: breadcrumb, title and meta, the steps card, then portrait clip tiles. */
export function ProjectSkeleton() {
  return (
    <SkeletonGroup label="Loading project" className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex flex-col gap-3">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-8 w-80 max-w-full" />
        <SkeletonText lines={1} className="w-72 max-w-full" />
      </div>
      <Skeleton className="h-48 w-full max-w-3xl" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 md:grid-cols-4 lg:grid-cols-5">
        {Array.from({ length: 5 }, (_, tile) => (
          <Skeleton key={tile} className={ASPECT_CLASS['9:16']} />
        ))}
      </div>
    </SkeletonGroup>
  );
}
