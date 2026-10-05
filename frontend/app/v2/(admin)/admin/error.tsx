'use client';

import { SegmentError, type SegmentErrorProps } from '@/app/v2/_platform/SegmentError';

export default function AdminError(props: Omit<SegmentErrorProps, 'segment'>) {
  return <SegmentError {...props} segment="admin" />;
}
