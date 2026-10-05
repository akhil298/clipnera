'use client';

import { SegmentError, type SegmentErrorProps } from '@/app/v2/_platform/SegmentError';

/** Area 4: keep unsaved pending ops in IndexedDB before offering a reload (frontend.md §1.3). */
export default function EditorError(props: Omit<SegmentErrorProps, 'segment'>) {
  return <SegmentError {...props} segment="editor" />;
}
