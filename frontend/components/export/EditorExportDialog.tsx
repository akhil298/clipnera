'use client';

import { useMemo } from 'react';

import type { ExportDialogSlot } from '@/components/editor/slots';

import { ExportDialog } from './ExportDialog';
import type { ExportSource } from './source';

/**
 * The editor's export dialog (`ExportDialogSlot`, components/editor/slots.ts). Exports the server
 * version Area 4 passes in. NEEDS-BACKEND: EB-24 — editor projects have no export route today, so
 * the render card reports that until `POST /exports` accepts `editor_project`.
 */
export const EditorExportDialog: ExportDialogSlot = ({ open, onOpenChange, projectId, title, version, timeline }) => {
  const source = useMemo<ExportSource>(() => ({ kind: 'editor', projectId, title, version, timeline }), [projectId, title, version, timeline]);
  return <ExportDialog source={source} open={open} onOpenChange={onOpenChange} />;
};
