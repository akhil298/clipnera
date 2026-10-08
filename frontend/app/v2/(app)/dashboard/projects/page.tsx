import type { Metadata } from 'next';
import { Suspense } from 'react';

import { ProjectsScreen } from '@/components/projects/list/ProjectsScreen';
import { ProjectsSkeleton } from '@/components/projects/list/ProjectsSkeleton';

export const metadata: Metadata = { title: 'Projects' };

/** Projects list (screens/01 §8). Data loads on the client: the token is not visible to the server yet. */
export default function ProjectsPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto w-full max-w-screen-2xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <ProjectsSkeleton />
        </div>
      }
    >
      <ProjectsScreen />
    </Suspense>
  );
}
