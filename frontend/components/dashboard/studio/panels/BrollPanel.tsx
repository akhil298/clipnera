"use client";
import React from 'react';
import { Plus, Trash2 } from 'lucide-react';
import type { BRollOverlay } from '@/lib/types';
import { ClipBrollPanel } from '../../ClipBrollPanel';
import { Section } from '../controls';
import { formatPrecise } from '../studioUtils';

const STOCK_BROLL: Array<{ title: string; category: BRollOverlay['category']; img: string }> = [
  {
    title: 'Analytics Surge Spike',
    category: 'growth',
    img: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600&auto=format&fit=crop&q=80',
  },
  {
    title: 'AI Cyber Matrix Code',
    category: 'tech',
    img: 'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=600&auto=format&fit=crop&q=80',
  },
  {
    title: 'Cash & Financial Growth',
    category: 'finance',
    img: 'https://images.unsplash.com/photo-1579621970563-ebec7560ff3e?w=600&auto=format&fit=crop&q=80',
  },
  {
    title: 'Shocked Viral Reaction',
    category: 'reaction',
    img: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=600&auto=format&fit=crop&q=80',
  },
];

interface BrollPanelProps {
  clipId: string;
  showCutaways: boolean;
  overlays: BRollOverlay[];
  currentTime: number;
  onAdd: (category: BRollOverlay['category'], imageUrl: string, title: string) => void;
  onRemove: (id: string) => void;
  onSeek: (time: number) => void;
}

export function BrollPanel({ clipId, showCutaways, overlays, currentTime, onAdd, onRemove, onSeek }: BrollPanelProps) {
  return (
    <>
      {showCutaways && (
        <Section title="AI cutaways">
          <ClipBrollPanel clipId={clipId} />
        </Section>
      )}

      <Section title="On this clip" aside={<small className="text-[11.5px] text-neutral-500">{overlays.length}</small>}>
        {overlays.length === 0 ? (
          <p className="text-[11.5px] text-neutral-500">No stock shots yet. Add one below at the playhead.</p>
        ) : (
          <div className="space-y-1.5">
            {overlays.map((b) => (
              <div key={b.id} className="flex items-center gap-2.5 p-2 rounded-[10px] border border-neutral-800 bg-neutral-900">
                <button type="button" onClick={() => onSeek(b.start + 0.01)} className="flex flex-1 min-w-0 items-center gap-2.5 text-left" title="Jump to this shot">
                  <img src={b.imageUrl} alt="" className="w-[30px] h-[30px] shrink-0 rounded-lg object-cover" />
                  <span className="min-w-0">
                    <b className="block truncate text-[12.5px] text-white">{b.title}</b>
                    <small className="font-mono text-[11px] text-neutral-500">
                      {formatPrecise(b.start)}–{formatPrecise(b.start + b.duration)}
                    </small>
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => onRemove(b.id)}
                  aria-label={`Remove ${b.title}`}
                  className="w-7 h-7 shrink-0 rounded-lg border border-neutral-700 inline-flex items-center justify-center text-neutral-400 hover:text-rose-400"
                >
                  <Trash2 className="w-3.5 h-3.5" aria-hidden />
                </button>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section title={`Add stock footage at ${formatPrecise(currentTime)}`}>
        <div className="grid grid-cols-2 gap-2">
          {STOCK_BROLL.map((item) => (
            <button
              key={item.title}
              type="button"
              onClick={() => onAdd(item.category, item.img, item.title)}
              className="group relative h-20 rounded-xl overflow-hidden border border-neutral-800 hover:border-amber-400 text-left"
            >
              <img src={item.img} alt="" className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
              <span className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/30 flex items-end justify-between gap-1 p-2">
                <span className="text-[10px] font-bold leading-tight text-white">{item.title}</span>
                <Plus className="w-3.5 h-3.5 shrink-0 text-amber-400" aria-hidden />
              </span>
            </button>
          ))}
        </div>
      </Section>
    </>
  );
}
