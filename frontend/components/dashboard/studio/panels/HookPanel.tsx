"use client";
import React from 'react';
import type { CaptionConfig, HookTransitionConfig } from '@/lib/types';
import { HookTransitionPanel } from '../../HookTransitionPanel';
import { RangeField, Section } from '../controls';

interface HookPanelProps {
  clipId: string;
  title: string;
  config: CaptionConfig;
  onCaptionChange: (changes: Partial<CaptionConfig>, coalesceKey?: string) => void;
  hookTransition: HookTransitionConfig;
  onHookTransitionChange: (next: HookTransitionConfig) => void;
}

export function HookPanel({ clipId, title, config, onCaptionChange, hookTransition, onHookTransitionChange }: HookPanelProps) {
  return (
    <>
      <Section title="Title overlay">
        <p className="rounded-[9px] border border-neutral-800 bg-neutral-900 px-2.5 py-2 text-[12.5px] text-neutral-200">
          {title.trim() || 'This clip has no title.'}
        </p>
        <div className="grid grid-cols-2 gap-3.5">
          <RangeField
            label="Size"
            value={config.titleFontSize}
            display={`${config.titleFontSize} px`}
            min={24}
            max={96}
            onChange={(v) => onCaptionChange({ titleFontSize: v }, 'titleFontSize')}
          />
          <RangeField
            label="Position"
            value={config.titlePositionY}
            display={`${config.titlePositionY}%`}
            min={2}
            max={40}
            onChange={(v) => onCaptionChange({ titlePositionY: v }, 'titlePositionY')}
          />
        </div>
      </Section>
      <Section title="Transition into the clip">
        <HookTransitionPanel clipId={clipId} config={hookTransition} onChange={onHookTransitionChange} />
      </Section>
    </>
  );
}
