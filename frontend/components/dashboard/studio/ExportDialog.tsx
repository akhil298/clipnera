"use client";
import React from 'react';
import { Download } from 'lucide-react';
import { exportStage } from './studioUtils';

interface ExportDialogProps {
  progress: number;
  complete: boolean;
  error: string | null;
  /** One line describing the finished file, e.g. "Hormozi captions · title · 9:16 HD". */
  summary: string;
  downloadLabel: string;
  canDownload: boolean;
  onDownload: () => void;
  onRetry: () => void;
  onClose: () => void;
}

export function ExportDialog({ progress, complete, error, summary, downloadLabel, canDownload, onDownload, onRetry, onClose }: ExportDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm animate-in fade-in">
      <div role="dialog" aria-modal="true" aria-label="Export" className="w-full max-w-md p-6 rounded-2xl bg-neutral-900 border border-neutral-800 text-center space-y-4 shadow-2xl">
        <div className="w-16 h-16 rounded-full bg-amber-500/15 border border-amber-500/30 mx-auto flex items-center justify-center text-amber-300">
          <Download className={`w-8 h-8 ${complete || error ? '' : 'animate-bounce'}`} aria-hidden />
        </div>

        <div>
          <h3 className="text-base font-bold text-white">
            {error ? 'Export failed' : complete ? 'Your clip is ready!' : 'Exporting your clip...'}
          </h3>
          <p className="text-xs text-neutral-400 mt-1">{error ?? (complete ? summary : exportStage(progress))}</p>
        </div>

        {!error && (
          <div className="space-y-1.5">
            <div className="h-3 w-full bg-neutral-950 rounded-full overflow-hidden border border-neutral-800">
              <div className="h-full bg-amber-500 transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>
            <p className="text-xs text-neutral-400 tabular-nums">{progress}% complete</p>
          </div>
        )}

        {error && (
          <div className="space-y-2 pt-2">
            <button
              type="button"
              onClick={onRetry}
              className="w-full py-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs shadow-lg shadow-amber-500/20"
            >
              Try again
            </button>
            <button type="button" onClick={onClose} className="w-full py-2 rounded-xl text-neutral-400 hover:text-white text-xs font-semibold">
              Close
            </button>
          </div>
        )}

        {complete && (
          <div className="space-y-2 pt-2">
            <button
              type="button"
              disabled={!canDownload}
              onClick={onDownload}
              className="w-full py-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs shadow-lg shadow-amber-500/20 disabled:opacity-50"
            >
              {downloadLabel}
            </button>
            <button type="button" onClick={onClose} className="w-full py-2 rounded-xl text-neutral-400 hover:text-white text-xs font-semibold">
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
