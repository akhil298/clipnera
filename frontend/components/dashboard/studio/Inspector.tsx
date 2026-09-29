"use client";
import React from 'react';
import { Crop, Film, Headphones, Music, Type, Zap } from 'lucide-react';
import type { StudioTool } from './studioUtils';

export const TOOLS: Array<{ id: StudioTool; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { id: 'captions', label: 'Captions', icon: Type },
  { id: 'hook', label: 'Hook', icon: Zap },
  { id: 'broll', label: 'B-roll', icon: Film },
  { id: 'sfx', label: 'Sound', icon: Music },
  { id: 'audio', label: 'Audio', icon: Headphones },
  { id: 'format', label: 'Format', icon: Crop },
];

export interface ToolBadges {
  brollCount: number;
  denoiseOn: boolean;
}

/** The dot or count a tool shows: B-roll count, preview-only Sound, live denoise. */
export function ToolBadge({ tool, badges }: { tool: StudioTool; badges: ToolBadges }) {
  if (tool === 'broll' && badges.brollCount > 0) {
    return (
      <span className="absolute top-0.5 right-1.5 min-w-[15px] h-[15px] px-[3px] rounded-full border border-neutral-700 bg-neutral-800 text-[9.5px] font-extrabold text-neutral-300 flex items-center justify-center tabular-nums">
        {badges.brollCount}
      </span>
    );
  }
  if (tool === 'sfx') {
    return <span className="absolute top-1 right-2.5 w-[7px] h-[7px] rounded-full border-[1.5px] border-dashed border-rose-400" title="Preview only" />;
  }
  if (tool === 'audio' && badges.denoiseOn) {
    return <span className="absolute top-1 right-2.5 w-[7px] h-[7px] rounded-full bg-emerald-400" title="Denoise on" />;
  }
  return null;
}

export function Inspector({
  tool,
  onTool,
  badges,
  children,
}: {
  tool: StudioTool;
  onTool: (tool: StudioTool) => void;
  badges: ToolBadges;
  children: React.ReactNode;
}) {
  return (
    <aside className="[grid-area:insp] flex flex-col min-h-0 min-w-0 border-l border-neutral-800 bg-neutral-900" aria-label="Edit tools">
      <div className="grid grid-cols-6 gap-0.5 p-2 border-b border-neutral-800" role="tablist">
        {TOOLS.map(({ id, label, icon: Icon }) => {
          const on = tool === id;
          return (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => onTool(id)}
              className={`relative flex flex-col items-center gap-1 pt-[7px] pb-1.5 rounded-[9px] text-[11px] font-semibold ${
                on ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:bg-neutral-800/60 hover:text-white'
              }`}
            >
              <Icon className={`w-4 h-4 ${on ? 'text-amber-400' : ''}`} />
              {label}
              <ToolBadge tool={id} badges={badges} />
            </button>
          );
        })}
      </div>
      <div role="tabpanel" className="flex-1 min-h-0 overflow-y-auto pb-3">
        {children}
      </div>
    </aside>
  );
}
