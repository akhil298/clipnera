import { SegmentNotFound } from '@/app/v2/_platform/SegmentNotFound';

export default function NotFound() {
  return (
    <SegmentNotFound
      title="Edit not found"
      description="It may have been deleted, or you don't have access to it."
      href="/dashboard/projects"
      linkLabel="Go to Projects"
    />
  );
}
