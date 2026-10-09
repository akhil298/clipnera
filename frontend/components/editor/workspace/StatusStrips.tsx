'use client';

import { Button } from '@/components/ui/Button';
import { Banner } from '@/components/ui/Alert';
import { WorkingText } from '@/components/ui/WorkingText';
import { type DocState, useDoc } from '@/lib/editor/store';

import { useEditor } from './context';

const selectPreview = (s: DocState) => s.preview;

/** Editor-level strips under the top bar, most severe first: offline, reconnecting, viewing an earlier version. */
export function StatusStrips() {
  const { connection, doc } = useEditor();
  const preview = useDoc(doc, selectPreview);
  return (
    <>
      {connection === 'offline' && (
        <Banner tone="warning" title="You're offline" live="status">
          Hand edits are kept on this device and sent when you're back. Runs already started keep going on our side.
        </Banner>
      )}
      {connection === 'reconnecting' && (
        <Banner tone="info" live="status">
          <WorkingText>Reconnecting. Your edit is still running.</WorkingText>
        </Banner>
      )}
      {preview && (
        <Banner
          tone="neutral"
          title={`Viewing an earlier version · ${preview.label}`}
          action={
            <Button size="sm" variant="secondary" onClick={doc.backToLatest}>
              Back to latest
            </Button>
          }
        >
          Editing is off until you go back to the latest version.
        </Banner>
      )}
    </>
  );
}
