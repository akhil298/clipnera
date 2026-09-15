import React from 'react';
import { Skeleton } from './Skeleton';

interface ImageSkeletonProps {
  className?: string;
  aspectRatio?: string;
}

export const ImageSkeleton: React.FC<ImageSkeletonProps> = ({ className = '', aspectRatio = 'aspect-video' }) => {
  return (
    <Skeleton className={`${aspectRatio} w-full rounded-lg ${className}`} />
  );
};
