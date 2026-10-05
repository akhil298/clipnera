import { SegmentNotFound } from '@/app/v2/_platform/SegmentNotFound';

export default function NotFound() {
  return (
    <SegmentNotFound
      title="Project not found"
      description="It may have been deleted, or it belongs to a workspace you’re not in. Check the workspace in the account menu."
      href="/dashboard/projects"
      linkLabel="See all projects"
    />
  );
}
