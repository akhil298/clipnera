import type { Metadata } from 'next';
import { OpenCutStudio } from '@/components/studio/OpenCutStudio';

export const metadata: Metadata = {
  title: 'Clipnera Studio',
  description: 'Edit your video on a multi-track timeline.',
};

export default async function StudioPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return <OpenCutStudio projectId={projectId} />;
}
