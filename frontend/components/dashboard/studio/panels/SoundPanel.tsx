"use client";
import React from 'react';
import { AlertTriangle, Trash2 } from 'lucide-react';
import type { SoundEffect } from '@/lib/types';
import { Section } from '../controls';
import { formatPrecise } from '../studioUtils';

export const SFX_LIBRARY: Array<{ type: SoundEffect['type']; name: string; detail: string; icon: string }> = [
  { type: 'whoosh', name: 'Whoosh', detail: 'Fast sweep', icon: '💨' },
  { type: 'ding', name: 'Ding', detail: 'Cash chime', icon: '🔔' },
  { type: 'pop', name: 'Pop', detail: 'Bubble impact', icon: '🫧' },
  { type: 'sub_drop', name: 'Sub drop', detail: '808 bass', icon: '💥' },
  { type: 'glitch', name: 'Glitch', detail: 'Cyber static', icon: '⚡' },
  { type: 'camera_shutter', name: 'Shutter', detail: 'Camera', icon: '📸' },
];

interface SoundPanelProps {
  effects: SoundEffect[];
  currentTime: number;
  onAdd: (type: SoundEffect['type'], name: string) => void;
  onRemove: (id: string) => void;
  onSeek: (time: number) => void;
}

export function SoundPanel({ effects, currentTime, onAdd, onRemove, onSeek }: SoundPanelProps) {
  return (
    <>
      <div className="px-4 pt-3">
        <p className="flex gap-2 rounded-[10px] border border-dashed border-rose-400/60 bg-rose-500/5 px-3 py-2 text-[11.5px] text-rose-100">
          <AlertTriangle className="w-3.5 h-3.5 mt-px shrink-0 text-rose-400" aria-hidden />
          <span>
            <b>Preview only.</b> Sound effects play here but aren&apos;t saved or exported yet.
          </span>
        </p>
      </div>

      <Section title="On this clip" aside={<small className="text-[11.5px] text-neutral-500">{effects.length}</small>}>
        {effects.length === 0 ? (
          <p className="text-[11.5px] text-neutral-500">None yet. Pick one below to drop it at the playhead.</p>
        ) : (
          <div className="space-y-1.5">
            {effects.map((s) => (
              <div key={s.id} className="flex items-center gap-2.5 p-2 rounded-[10px] border border-neutral-800 bg-neutral-900">
                <button type="button" onClick={() => onSeek(s.time)} className="flex flex-1 min-w-0 items-center gap-2.5 text-left" title="Jump to this sound">
                  <span className="w-[30px] h-[30px] shrink-0 rounded-lg bg-neutral-800 flex items-center justify-center text-sm">
                    {SFX_LIBRARY.find((l) => l.type === s.type)?.icon ?? '🔊'}
                  </span>
                  <span className="min-w-0">
                    <b className="block truncate text-[12.5px] text-white">{s.name}</b>
                    <small className="font-mono text-[11px] text-neutral-500">{formatPrecise(s.time)}</small>
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => onRemove(s.id)}
                  aria-label={`Remove ${s.name}`}
                  className="w-7 h-7 shrink-0 rounded-lg border border-neutral-700 inline-flex items-center justify-center text-neutral-400 hover:text-rose-400"
                >
                  <Trash2 className="w-3.5 h-3.5" aria-hidden />
                </button>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title={`Add at ${formatPrecise(currentTime)}`}>
        <div className="grid grid-cols-2 gap-1.5">
          {SFX_LIBRARY.map((sfx) => (
            <button
              key={sfx.type}
              type="button"
              onClick={() => onAdd(sfx.type, sfx.name)}
              className="flex items-center gap-2 p-1.5 rounded-[10px] border border-neutral-800 bg-neutral-900 hover:border-emerald-500/50 hover:bg-emerald-500/5 text-left"
            >
              <span className="w-[26px] h-[26px] shrink-0 rounded-lg bg-neutral-800 flex items-center justify-center text-sm">{sfx.icon}</span>
              <span className="min-w-0">
                <b className="block truncate text-[12px] text-white">{sfx.name}</b>
                <small className="block truncate text-[10.5px] text-neutral-500">{sfx.detail}</small>
              </span>
            </button>
          ))}
        </div>
      </Section>
    </>
  );
}
