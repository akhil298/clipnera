"use client";
import React from 'react';
import { Info, Lock } from 'lucide-react';
import type { AspectRatio, AutoZoomConfig } from '@/lib/types';
import { canUseAspectRatio, useEntitlements } from '@/hooks/useEntitlements';
import { NotWiredBadge } from '@/components/ui/NotWiredBadge';
import { UpgradeHint } from '../../ProLockBadge';
import { Note, RangeField, Section, Switch } from '../controls';
import { EXPORT_SIZE } from '../studioUtils';

const RATIOS: Array<{ ratio: AspectRatio; name: string; w: number; h: number }> = [
  { ratio: '9:16', name: 'Vertical', w: 18, h: 32 },
  { ratio: '4:5', name: 'Portrait', w: 24, h: 30 },
  { ratio: '1:1', name: 'Square', w: 28, h: 28 },
  { ratio: '16:9', name: 'Wide', w: 34, h: 19 },
];

interface FormatPanelProps {
  aspectRatio: AspectRatio;
  onAspectRatio: (ratio: AspectRatio) => void;
  autoZoom: AutoZoomConfig;
  onAutoZoom: (changes: Partial<AutoZoomConfig>, coalesceKey?: string) => void;
}

export function FormatPanel({ aspectRatio, onAspectRatio, autoZoom, onAutoZoom }: FormatPanelProps) {
  const { entitlements, promptUpgrade } = useEntitlements();
  return (
    <>
      <Section title="Aspect ratio">
        <div className="grid grid-cols-4 gap-1.5">
          {RATIOS.map(({ ratio, name, w, h }) => {
            const unlocked = canUseAspectRatio(entitlements, ratio);
            const active = aspectRatio === ratio;
            return (
              <button
                key={ratio}
                type="button"
                onClick={() => (unlocked ? onAspectRatio(ratio) : promptUpgrade(`The ${ratio} output format`))}
                aria-pressed={active}
                aria-disabled={!unlocked}
                className={`relative flex flex-col items-center gap-1.5 rounded-[10px] border-[1.5px] bg-neutral-900 px-1 pt-2.5 pb-2 ${
                  active ? 'border-amber-400' : 'border-neutral-800 hover:border-neutral-700'
                }`}
              >
                <span
                  className={`rounded-[3px] border-[1.5px] ${active ? 'border-amber-400 bg-amber-500/10' : 'border-neutral-500'}`}
                  style={{ width: w, height: h }}
                />
                <b className="text-xs text-white">{ratio}</b>
                <small className="text-center text-[9.5px] leading-tight text-neutral-500">
                  {name}
                  <br />
                  {EXPORT_SIZE[ratio]}
                </small>
                {!unlocked && <Lock className="absolute top-1 right-1 w-2.5 h-2.5 text-amber-300" aria-label="Paid plans" />}
              </button>
            );
          })}
        </div>
        {entitlements.aspect_ratios.length < RATIOS.length && (
          <UpgradeHint message="Unlock 1:1, 4:5 and 16:9 exports with a paid plan." onUpgrade={() => promptUpgrade('Additional output formats')} />
        )}
      </Section>

      <Section
        title="Auto-zoom"
        aside={
          <span className="flex items-center gap-2">
            <NotWiredBadge label="Preview only" reason="Auto-zoom is shown in the preview but not applied to exports yet." />
            <Switch checked={autoZoom.enabled} onChange={(on) => onAutoZoom({ enabled: on })} label="Auto-zoom" />
          </span>
        }
      >
        <Note icon={<Info />}>Punches in on emphasised words. Shows in the preview; the export doesn&apos;t include it yet.</Note>
        <RangeField
          label="Zoom"
          value={autoZoom.scale}
          display={`${autoZoom.scale.toFixed(2)}×`}
          min={1.05}
          max={1.35}
          step={0.05}
          onChange={(v) => onAutoZoom({ scale: v }, 'zoomScale')}
        />
      </Section>
    </>
  );
}
