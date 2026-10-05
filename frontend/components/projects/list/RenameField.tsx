'use client';

import { useRef, useState } from 'react';

import { Input } from '@/components/ui';

/** backend/clip/model.py `VideoProject.title` is String(500). */
const MAX_TITLE = 500;

/** Inline rename: Enter or leaving the field saves, Escape cancels. */
export function RenameField({
  title,
  onSave,
  onCancel,
}: {
  title: string;
  onSave: (title: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(title);
  // Enter and the blur that follows unmounting must not both fire.
  const done = useRef(false);
  const finish = (save: boolean) => {
    if (done.current) return;
    done.current = true;
    const next = value.trim();
    if (save && next && next !== title) onSave(next);
    else onCancel();
  };

  return (
    <Input
      aria-label="Project name"
      size="sm"
      autoFocus
      onFocus={(event) => event.currentTarget.select()}
      value={value}
      maxLength={MAX_TITLE}
      onChange={(event) => setValue(event.target.value)}
      onBlur={() => finish(true)}
      onKeyDown={(event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          finish(true);
        } else if (event.key === 'Escape') {
          event.preventDefault();
          event.stopPropagation();
          finish(false);
        }
      }}
      className="relative z-cn-raised min-w-0 flex-1"
    />
  );
}
