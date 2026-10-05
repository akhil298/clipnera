'use client';

import { SegmentError, type SegmentErrorProps } from '@/app/v2/_platform/SegmentError';

export default function DashboardError(props: Omit<SegmentErrorProps, 'segment'>) {
  return <SegmentError {...props} segment="dashboard" />;
}
