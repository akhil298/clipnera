'use client';

import Link from 'next/link';

import { buttonClasses } from '@/components/ui';
import { useSignedIn } from '@/lib/marketing/useSignedIn';

const EDITOR_PATH = '/dashboard/editor';

/** Opens the editor, through sign-in when needed. */
export function EditorLink() {
  const signedIn = useSignedIn();
  return (
    <Link href={signedIn ? EDITOR_PATH : `/login?next=${EDITOR_PATH}`} className={buttonClasses({ variant: 'secondary' })}>
      Open the editor
    </Link>
  );
}
