'use client';

import { useQuery } from '@tanstack/react-query';
import { Clapperboard, RotateCcw, TriangleAlert } from 'lucide-react';
import Link from 'next/link';
import { notFound } from 'next/navigation';

import { Button, buttonClasses } from '@/components/ui/Button';
import { getEditorProject } from '@/lib/api/editor/projects';
import { isFeatureDisabled, isNotFound } from '@/lib/api/errors';
import { editorMessage } from '@/lib/api/messages/editor';
import { editorKeys } from '@/lib/query/keys/editor';

import { EditorFrameSkeleton } from './workspace/EditorFrameSkeleton';
import { EditorRoot } from './workspace/EditorRoot';
import { EditorStateCard } from './workspace/EditorStateCard';

export interface EditorClientProps {
  editorProjectId: string;
  /** `?sim=1` outside production: the dev run simulator drives the conversation. */
  simulate?: boolean;
}

const BACK = { href: '/dashboard/editor', label: 'Projects' };

/**
 * Loads an editor project (`GET /editor/projects/{id}`) and opens the workspace on it. The query is
 * only the first snapshot; from then on the doc store owns the live document (frontend.md §3.4).
 */
export function EditorClient({ editorProjectId, simulate = false }: EditorClientProps) {
  const query = useQuery({
    queryKey: editorKeys.project(editorProjectId),
    queryFn: ({ signal }) => getEditorProject(editorProjectId, signal),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  if (query.data) return <EditorRoot key={query.data.id} project={query.data} simulate={simulate} />;
  if (query.isPending) return <EditorFrameSkeleton />;
  if (isNotFound(query.error)) notFound();
  if (isFeatureDisabled(query.error)) {
    return (
      <EditorStateCard
        icon={<Clapperboard />}
        title="The editor isn't on for your account yet"
        description="It's being rolled out in stages. Your clips are in Projects."
        back={BACK}
        action={
          <Link href="/dashboard/projects" className={buttonClasses({ variant: 'secondary' })}>
            Go to Projects
          </Link>
        }
      />
    );
  }
  const code = (query.error as { code?: string } | null)?.code;
  return (
    <EditorStateCard
      icon={<TriangleAlert />}
      title="I couldn't open this project"
      description={`${editorMessage(code, query.error?.message).text} Edits you made earlier are kept on this device.`}
      back={BACK}
      action={
        <Button leadingIcon={<RotateCcw />} loading={query.isFetching} loadingLabel="Trying again" onClick={() => void query.refetch()}>
          Try again
        </Button>
      }
    />
  );
}
