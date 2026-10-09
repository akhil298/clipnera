'use client';

/**
 * Version history slot (02-editor §10), opened by the top bar's History button and ⌘⇧H. Filled by V1:
 * replace the body with the version list, viewing and restore. The frame owns the Drawer.
 *
 * Props contract (stable): none. From `useEditor()`: `history.open` / `history.setOpen`, `doc`
 * (`viewVersion`, `backToLatest`, `replaceServer`), `project`. NEEDS-BACKEND: EB-10/EB-11 (versions).
 */
import { History } from 'lucide-react';

import { ZoneNote } from '../Zone';

export function HistoryZone() {
  return <ZoneNote icon={<History />} title="No versions yet" description="Each prompt and each pause in hand editing saves one." />;
}
