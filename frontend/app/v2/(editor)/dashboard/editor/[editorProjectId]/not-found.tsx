import { SegmentNotFound } from '@/app/v2/_platform/SegmentNotFound';

export default function NotFound() {
  return (
    <SegmentNotFound
      title="Project not found"
      description="It may have been deleted, or it's in a workspace you're not in."
      href="/dashboard/editor"
      linkLabel="See all projects"
    />
  );
}
