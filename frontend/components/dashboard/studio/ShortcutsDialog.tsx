"use client";
import React from 'react';
import { X } from 'lucide-react';

const SHORTCUTS: Array<[string, string[]]> = [
  ['Play or pause', ['Space']],
  ['Back or forward 2 s', ['J', 'L']],
  ['Cut selected words', ['⌫']],
  ['Highlight selected words', ['H']],
  ['Undo', ['⌘Z']],
  ['Redo', ['⇧⌘Z']],
  ['Previous or next clip', ['[', ']']],
  ['Export', ['⌘E']],
  ['Back to clips', ['Esc']],
  ['Show shortcuts', ['?']],
];

export function ShortcutsDialog({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Keyboard shortcuts"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-2xl border border-neutral-800 bg-neutral-900 p-5 shadow-2xl"
      >
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold text-white">Keyboard shortcuts</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="w-8 h-8 rounded-[9px] inline-flex items-center justify-center text-neutral-400 hover:bg-neutral-800 hover:text-white"
          >
            <X className="w-4 h-4" aria-hidden />
          </button>
        </div>
        <dl className="text-[13px]">
          {SHORTCUTS.map(([label, keys]) => (
            <div key={label} className="flex items-center justify-between gap-3 border-b border-dashed border-neutral-800 py-1.5 last:border-b-0">
              <dt className="text-neutral-300">{label}</dt>
              <dd className="flex gap-1">
                {keys.map((k) => (
                  <kbd key={k} className="rounded-[5px] border border-b-2 border-neutral-700 bg-neutral-950 px-1.5 py-px font-mono text-[11.5px] text-neutral-200">
                    {k}
                  </kbd>
                ))}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
