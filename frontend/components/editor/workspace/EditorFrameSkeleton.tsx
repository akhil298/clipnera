import { Skeleton, SkeletonGroup } from '@/components/ui/Skeleton';

/** The editor's loading frame (02-editor §2.3): top bar, rail, empty stage, three tracks and the conversation column. */
export function EditorFrameSkeleton({ label = 'Opening the editor' }: { label?: string }) {
  return (
    <SkeletonGroup label={label} className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-12 shrink-0 items-center gap-3 border-b border-cn-border px-3">
        <Skeleton className="h-6 w-20" />
        <Skeleton className="h-4 w-48 max-w-full" />
        <div className="flex-1" />
        <Skeleton className="h-8 w-24" />
      </div>
      <div className="flex min-h-0 flex-1 gap-1 p-1">
        <div className="hidden w-12 shrink-0 flex-col items-center gap-2 py-1 md:flex">
          {Array.from({ length: 5 }, (_, tool) => (
            <Skeleton key={tool} className="size-9" />
          ))}
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="min-h-0 flex-1 rounded-cn-lg bg-cn-stage" />
          <div className="flex h-40 shrink-0 flex-col gap-2 rounded-cn-lg bg-cn-surface p-3 md:h-52">
            <Skeleton className="h-3 w-full" />
            {Array.from({ length: 3 }, (_, track) => (
              <Skeleton key={track} className="h-8 w-full" />
            ))}
          </div>
        </div>
        <div className="hidden w-80 shrink-0 flex-col gap-3 rounded-cn-lg bg-cn-surface p-3 lg:flex">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-24 w-full" />
          <div className="flex-1" />
          <Skeleton className="h-20 w-full" />
        </div>
      </div>
    </SkeletonGroup>
  );
}
