"use client";
import React, { useState } from 'react';
import { AlertTriangle, Ban, CheckCircle2, Info } from 'lucide-react';
import type { AspectRatio, CaptionConfig, CaptionPreset } from '@/lib/types';
import { getAllCaptionStyles } from '@/lib/utils/captionStyles';
import { EMOJI_COLLECTIONS } from '@/lib/data/emojiCollections';
import { canUseCaptionStyle, useEntitlements } from '@/hooks/useEntitlements';
import { CaptionStylePreview } from '../../CaptionStylePreview';
import { ProLockBadge } from '../../ProLockBadge';
import { Chip, ColorSwatches, Note, RangeField, Section, Switch } from '../controls';
import { CAPTION_Y_MAX, CAPTION_Y_MIN, PreviewMode, captionsClear, safeZoneFor } from '../studioUtils';

// Five styles plus the "No captions" tile fill two rows of three.
const COLLAPSED_STYLE_COUNT = 5;
const ACTIVE_COLOURS = ['#f59e0b', '#22c55e', '#facc15', '#ec4899', '#38bdf8'];
const EMPHASIS_COLOURS = ['#a78bfa', '#f472b6', '#fb923c', '#4ade80', '#ffffff'];
const POSITIONS: Array<[string, number]> = [
  ['Top', 22],
  ['Middle', 50],
  ['Lower third', 62],
];

interface CaptionsPanelProps {
  config: CaptionConfig;
  onChange: (changes: Partial<CaptionConfig>, coalesceKey?: string) => void;
  /** Picking a style also turns captions on. */
  onPickPreset: (preset: CaptionPreset) => void;
  captionsOn: boolean;
  onTurnCaptionsOff: () => void;
  preview: PreviewMode;
  aspectRatio: AspectRatio;
}

export function CaptionsPanel({ config, onChange, onPickPreset, captionsOn, onTurnCaptionsOff, preview, aspectRatio }: CaptionsPanelProps) {
  const { entitlements, promptUpgrade } = useEntitlements();
  const [showAllStyles, setShowAllStyles] = useState(false);
  const styles = getAllCaptionStyles();
  // Keep the chosen style in view even when it sits past the first six.
  const shown = showAllStyles
    ? styles
    : styles.slice(0, COLLAPSED_STYLE_COUNT).concat(
        styles.findIndex((s) => s.id === config.preset) >= COLLAPSED_STYLE_COUNT ? styles.filter((s) => s.id === config.preset) : [],
      );
  const zone = safeZoneFor(preview);

  return (
    <>
      <Section
        title="Style"
        aside={
          <button type="button" onClick={() => setShowAllStyles((v) => !v)} className="text-[11.5px] font-bold text-amber-300 hover:text-amber-200">
            {showAllStyles ? 'Show fewer' : `See all ${styles.length}`}
          </button>
        }
      >
        <div className="grid grid-cols-3 gap-1.5">
          <button
            type="button"
            onClick={onTurnCaptionsOff}
            aria-pressed={!captionsOn}
            title="Export the video without captions"
            className={`h-[62px] rounded-[10px] border-[1.5px] bg-neutral-900 flex flex-col items-center justify-center gap-1 text-neutral-400 ${
              captionsOn ? 'border-neutral-800 hover:border-neutral-700 hover:text-neutral-200' : 'border-amber-400 ring-[3px] ring-amber-500/20 text-amber-300'
            }`}
          >
            <Ban className="w-4 h-4" aria-hidden />
            <span className="text-[9.5px] font-bold">No captions</span>
          </button>
          {shown.map((style) => {
            const unlocked = canUseCaptionStyle(entitlements, style.id);
            const active = captionsOn && config.preset === style.id;
            return (
              <button
                key={style.id}
                type="button"
                onClick={() => (unlocked ? onPickPreset(style.id) : promptUpgrade(`The ${style.brandName} caption style`))}
                aria-pressed={active}
                aria-disabled={!unlocked}
                title={style.description}
                className={`relative h-[62px] rounded-[10px] border-[1.5px] overflow-hidden ${
                  active ? 'border-amber-400 ring-[3px] ring-amber-500/20' : 'border-neutral-800 hover:border-neutral-700'
                } ${unlocked ? '' : 'opacity-75'}`}
              >
                <CaptionStylePreview config={style.config} words={['MOST', 'NEVER']} fontSize={13} className="absolute inset-0 !rounded-none" />
                <span className="absolute inset-x-0 bottom-0 bg-black/60 py-0.5 text-center text-[9.5px] font-bold text-neutral-200 truncate px-1">
                  {style.name}
                </span>
                {!unlocked && <ProLockBadge feature={`The ${style.brandName} style`} className="absolute top-1 right-1 !px-1 !text-[9px]" />}
              </button>
            );
          })}
        </div>
        {!captionsOn && <Note icon={<Info />}>Captions are off, so the video exports without them. Pick a style to add them back.</Note>}
      </Section>

      <Section title="Look">
        <div className="space-y-2.5">
          <ColorSwatches label="Active word" value={config.highlightColor} options={ACTIVE_COLOURS} onChange={(c) => onChange({ highlightColor: c }, 'highlightColor')} />
          <ColorSwatches
            label={config.hasBgBox ? 'Word pill' : 'Highlighted words'}
            value={config.secondaryHighlightColor}
            options={EMPHASIS_COLOURS}
            onChange={(c) => onChange({ secondaryHighlightColor: c }, 'secondaryHighlightColor')}
          />
        </div>
        <div className="grid grid-cols-2 gap-3.5">
          <RangeField label="Size" value={config.fontSize} display={`${config.fontSize} px`} min={8} max={72} onChange={(v) => onChange({ fontSize: v }, 'fontSize')} />
          <RangeField
            label="Shadow"
            value={config.shadowIntensity}
            display={`${config.shadowIntensity.toFixed(1)}×`}
            min={0}
            max={1}
            step={0.1}
            onChange={(v) => onChange({ shadowIntensity: v }, 'shadowIntensity')}
          />
        </div>
      </Section>

      <Section title="Motion" aside={<small className="text-[11.5px] text-neutral-500 capitalize">{config.animation} · {config.animationSpeed.toFixed(2)}×</small>}>
        <div className="flex flex-wrap gap-1.5">
          {(['pop', 'karaoke', 'wave', 'glow'] as const).map((anim) => (
            <Chip key={anim} active={config.animation === anim} onClick={() => onChange({ animation: anim })}>
              <span className="capitalize">{anim}</span>
            </Chip>
          ))}
        </div>
        <RangeField
          label="Speed"
          value={config.animationSpeed}
          display={`${config.animationSpeed.toFixed(2)}×`}
          min={0.25}
          max={3}
          step={0.25}
          onChange={(v) => onChange({ animationSpeed: v }, 'animationSpeed')}
        />
      </Section>

      <Section title="Position" aside={<small className="text-[11.5px] text-neutral-500 tabular-nums">{config.positionY}% from top</small>}>
        <div className="flex flex-wrap gap-1.5">
          {POSITIONS.map(([label, y]) => (
            <Chip key={label} active={Math.abs(config.positionY - y) < 6} onClick={() => onChange({ positionY: y })}>
              {label}
            </Chip>
          ))}
        </div>
        <RangeField
          label="Vertical position"
          value={config.positionY}
          display={`${config.positionY}%`}
          min={CAPTION_Y_MIN}
          max={CAPTION_Y_MAX}
          onChange={(v) => onChange({ positionY: v }, 'positionY')}
        />
        <Note icon={<Info />}>Or drag the caption on the video. It snaps to the safe area.</Note>
        {aspectRatio === '9:16' &&
          (captionsClear(config.positionY, zone) ? (
            <Note tone="ok" icon={<CheckCircle2 />}>Clear of {zone.name} buttons and text</Note>
          ) : (
            <Note tone="warn" icon={<AlertTriangle />}>{zone.name} text covers this spot</Note>
          ))}
      </Section>

      <Section
        title="Emojis"
        aside={<Switch checked={config.emojisEnabled} onChange={(on) => onChange({ emojisEnabled: on })} label="Auto emojis" />}
      >
        {config.emojisEnabled ? (
          <div className="flex gap-1.5 overflow-x-auto pb-1 [scrollbar-width:thin]">
            <Chip active={!config.emojiCollection} onClick={() => onChange({ emojiCollection: undefined })}>
              None
            </Chip>
            {EMOJI_COLLECTIONS.map((col) => (
              <Chip
                key={col.id}
                active={config.emojiCollection === col.id}
                title={col.name}
                onClick={() => onChange({ emojiCollection: config.emojiCollection === col.id ? undefined : col.id })}
              >
                {col.emoji}
              </Chip>
            ))}
          </div>
        ) : (
          <p className="text-[11.5px] text-neutral-500">Turn on to add emojis to key words and the title.</p>
        )}
      </Section>

      <Section
        title="Background"
        defaultOpen={false}
        aside={<Switch checked={config.hasBgBox} onChange={(on) => onChange({ hasBgBox: on })} label="Dark box behind captions" />}
      >
        <p className="text-[11.5px] text-neutral-500">
          {config.hasBgBox ? 'Captions sit on a dark box; the spoken word gets a coloured pill.' : 'Captions sit straight on the video.'}
        </p>
      </Section>
    </>
  );
}
