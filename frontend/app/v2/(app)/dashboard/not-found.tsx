import { SegmentNotFound } from '@/app/v2/_platform/SegmentNotFound';

/** In-shell 404: the sidebar and top bar keep working (screens/01 §6). */
export default function NotFound() {
  return (
    <SegmentNotFound
      description="The link may be old or mistyped. Everything else is where you left it."
      href="/dashboard"
      linkLabel="Go to Home"
    />
  );
}
