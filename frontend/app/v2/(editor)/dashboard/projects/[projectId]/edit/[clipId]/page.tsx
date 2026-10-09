import { ClipModeFrame } from '@/components/editor/workspace/ClipModeFrame';

interface PageProps {
  params: Promise<{ projectId: string; clipId: string }>;
}

/** `/dashboard/projects/[projectId]/edit/[clipId]`: the editor frame in clip mode (02-editor §12); CS1 fills it. */
export default async function Page({ params }: PageProps) {
  const { projectId, clipId } = await params;
  return <ClipModeFrame projectId={projectId} clipId={clipId} />;
}
