'use client';

import { type ReactNode, useCallback, useEffect, useMemo, useState } from 'react';

import { ExportDialog } from './ExportDialog';
import { useExportJobs } from './ExportJobs';
import { type ExportTarget, toSource } from './source';
import type { ExportJob } from './store';

export interface UseExportOptions {
  /** Bind ⌘E / Ctrl+E to open the dialog (editor §11, Keyboard). */
  shortcut?: boolean;
}

export interface UseExport {
  open: () => void;
  isOpen: boolean;
  /** Render this once; it is the dialog, closed until `open()`. */
  dialog: ReactNode;
  /** This session's exports of the target's project, newest first. */
  jobs: ExportJob[];
}

/**
 * Opens the export dialog for one clip, a set of a project's clips, or an editor project
 * (`ExportSource`). Shared by the Project page and the editor.
 */
export function useExport(target: ExportTarget | null, { shortcut = false }: UseExportOptions = {}): UseExport {
  const [isOpen, setOpen] = useState(false);
  const source = useMemo(() => (target ? toSource(target) : null), [target]);
  const jobs = useExportJobs(source?.projectId);
  const open = useCallback(() => setOpen(true), []);

  useEffect(() => {
    if (!shortcut || !source) return;
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === 'e') {
        event.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [shortcut, source]);

  const dialog = source ? <ExportDialog source={source} open={isOpen} onOpenChange={setOpen} /> : null;
  return { open, isOpen, dialog, jobs };
}
