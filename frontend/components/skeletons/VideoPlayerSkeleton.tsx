import React from 'react';
import { Skeleton } from './Skeleton';

interface VideoPlayerSkeletonProps {
  aspectRatio?: '9:16' | '1:1' | '16:9';
}

export const VideoPlayerSkeleton: React.FC<VideoPlayerSkeletonProps> = ({ aspectRatio = '9:16' }) => {
  const aspectClass =
    aspectRatio === '9:16'
      ? 'aspect-[9/16]'
      : aspectRatio === '1:1'
        ? 'aspect-square'
        : 'aspect-video';

  return (
    <div className={`relative rounded-2xl bg-black border-2 border-neutral-800 shadow-2xl overflow-hidden flex items-center justify-center ${aspectClass}`}>
      <Skeleton className="absolute inset-0" />
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="w-16 h-16 rounded-full bg-neutral-800/60 flex items-center justify-center">
          <Skeleton className="w-8 h-8 rounded-full" />
        </div>
      </div>
    </div>
  );
};
