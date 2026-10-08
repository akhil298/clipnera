import type { Metadata } from 'next';

import { ProjectDetail } from '@/components/projects/detail/ProjectDetail';

export const metadata: Metadata = { title: 'Project' };

/** Server entry; the data lives in the client island because the session token is client-side (01-platform-api). */
export default async function Page({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return <ProjectDetail key={projectId} projectId={projectId} />;
}
