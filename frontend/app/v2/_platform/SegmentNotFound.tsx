import { SearchX } from 'lucide-react';
import Link from 'next/link';

import { buttonClasses } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';

export interface SegmentNotFoundProps {
  title?: string;
  description?: string;
  href: string;
  linkLabel: string;
}

/** The body of every v2 `not-found.tsx`. */
export function SegmentNotFound({
  title = "This page doesn't exist",
  description = 'The link may be old, or the page has moved.',
  href,
  linkLabel,
}: SegmentNotFoundProps) {
  return (
    <section className="flex flex-1 items-center justify-center px-4 py-12">
      <EmptyState
        icon={<SearchX />}
        title={title}
        description={description}
        action={
          <Link href={href} className={buttonClasses({ variant: 'secondary' })}>
            {linkLabel}
          </Link>
        }
      />
    </section>
  );
}
