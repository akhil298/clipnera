'use client';

import { SAVE_STATE_TEXT } from '@/lib/api/messages/editor';
import { type DocStore, selectSaveState, useDoc } from '@/lib/editor/store';
import { cx, focusRing } from '@/lib/design/styles';

/** "Saved · Saving · Not saved (Retry) · Offline" under the title (02-editor §2.1). */
export function SaveState({ doc, compact = false }: { doc: DocStore; compact?: boolean }) {
  const save = useDoc(doc, selectSaveState);
  return (
    <span role="status" className="flex min-w-0 items-center gap-1.5 text-cn-caption text-cn-fg-muted">
      <span className={cx('truncate', save === 'error' && 'text-cn-danger-text')}>{compact && save === 'offline' ? 'Offline' : SAVE_STATE_TEXT[save]}</span>
      {save === 'error' && (
        <button type="button" onClick={() => void doc.retry()} className={cx('shrink-0 rounded-cn-xs font-semibold text-cn-fg underline-offset-2 hover:underline', focusRing)}>
          Retry
        </button>
      )}
    </span>
  );
}
