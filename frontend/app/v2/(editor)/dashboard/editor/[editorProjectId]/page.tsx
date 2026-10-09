import { EditorClient } from '@/components/editor/EditorClient';

interface PageProps {
  params: Promise<{ editorProjectId: string }>;
  searchParams: Promise<{ sim?: string }>;
}

/** `/dashboard/editor/[editorProjectId]` (02-editor §2). `?sim=1` runs the dev simulator outside production. */
export default async function Page({ params, searchParams }: PageProps) {
  const [{ editorProjectId }, { sim }] = await Promise.all([params, searchParams]);
  return <EditorClient editorProjectId={editorProjectId} simulate={process.env.NODE_ENV !== 'production' && sim === '1'} />;
}
