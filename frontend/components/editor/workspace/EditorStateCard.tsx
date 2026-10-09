import { ChevronLeft } from 'lucide-react';
import Link from 'next/link';
import type { ReactNode } from 'react';

import { EmptyState } from '@/components/ui/EmptyState';
import { cx, focusRing } from '@/lib/design/styles';

export interface EditorStateCardProps {
  icon: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
  back: { href: string; label: string };
}

/** A whole-editor state (flag off, couldn't load) inside the editor frame: a bare top bar and one centred message. */
export function EditorStateCard({ icon, title, description, action, back }: EditorStateCardProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-12 shrink-0 items-center border-b border-cn-border px-2 sm:px-3">
        <Link
          href={back.href}
          className={cx('inline-flex h-8 items-center gap-1 rounded-cn-sm px-1.5 text-cn-label font-semibold text-cn-fg-secondary hover:bg-cn-surface-hover hover:text-cn-fg', focusRing)}
        >
          <ChevronLeft aria-hidden className="size-4" />
          {back.label}
        </Link>
      </div>
      <div className="flex min-h-0 flex-1 items-center justify-center p-4">
        <EmptyState icon={icon} title={title} description={description} action={action} />
      </div>
    </div>
  );
}
