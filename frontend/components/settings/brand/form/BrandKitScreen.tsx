'use client';

import { useQuery } from '@tanstack/react-query';
import { CircleAlert, RotateCcw } from 'lucide-react';

import { Button, EmptyState, Skeleton, SkeletonGroup } from '@/components/ui';
import { getBrandKit } from '@/lib/api/brand/kit';
import { brandKeys } from '@/lib/query/keys/brand';

import { BrandKitEditor } from './BrandKitEditor';

const MINUTE = 60_000;

function Header() {
  return (
    <header className="space-y-1">
      <h1 className="text-cn-title-lg font-semibold text-cn-fg">Brand kit</h1>
      <p className="max-w-2xl text-cn-body text-cn-fg-secondary">
        Applied to every new clip: watermark, fonts, colours, default caption style and end card. Your channel intro plays before every export.
      </p>
    </header>
  );
}

/**
 * `/dashboard/brand-kit`. The form only renders once the saved kit has loaded,
 * so a failed load can never be saved over (screens/03 §16.5).
 */
export function BrandKitScreen() {
  const kit = useQuery({ queryKey: brandKeys.kit(), queryFn: ({ signal }) => getBrandKit(signal), staleTime: 5 * MINUTE });

  return (
    <div className="flex flex-1 flex-col gap-6 motion-safe:animate-in motion-safe:fade-in motion-safe:duration-cn-fast">
      <Header />
      {kit.isPending ? (
        <SkeletonGroup label="Loading your brand kit" className="grid gap-6 lg:grid-cols-12">
          <Skeleton className="h-96 rounded-cn-lg lg:col-span-7" />
          <Skeleton className="h-96 rounded-cn-lg lg:col-span-5" />
        </SkeletonGroup>
      ) : kit.isError ? (
        <EmptyState
          icon={<CircleAlert />}
          title="Your brand kit didn't load"
          description="Your saved kit is safe. I don't show the form until it loads, so nothing can be overwritten by mistake."
          action={
            <Button variant="secondary" leadingIcon={<RotateCcw />} loading={kit.isFetching} loadingLabel="Trying again" onClick={() => void kit.refetch()}>
              Try again
            </Button>
          }
        />
      ) : (
        <BrandKitEditor saved={kit.data} />
      )}
    </div>
  );
}
