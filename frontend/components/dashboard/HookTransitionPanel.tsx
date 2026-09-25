'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Check, Search, Shuffle, Sparkles, Wand2 } from 'lucide-react';
import { hookTransitionApi } from '@/lib/api';
import { useHookTransitionCatalog } from '@/hooks/useHookTransitionCatalog';
import type {
  HookTransitionApplied,
  HookTransitionCatalog,
  HookTransitionConfig,
  HookTransitionMode,
  HookTransitionPart,
  HookTransitionPreset,
} from '@/lib/types';

interface HookTransitionPanelProps {
  clipId: string;
  config: HookTransitionConfig;
  onChange: (config: HookTransitionConfig) => void;
}

// Mirrors CUSTOM_DEFAULTS in backend/hook_transitions/resolver.py: what a mix
// starts from when no preset is chosen.
const CUSTOM_BASE: Omit<HookTransitionPreset, 'id' | 'name' | 'group' | 'fits' | 'moods'> = {
  source: 'freeze_frame',
  effects: [],
  sound: 'whoosh',
  impact: 'none',
  impact_sound: null,
  text: null,
  text_style: 'bold_white',
  duration: 0.8,
};

const MODES: Array<{ id: HookTransitionMode; label: string }> = [
  { id: 'auto', label: 'Auto' },
  { id: 'preset', label: 'Presets' },
  { id: 'custom', label: 'Mix' },
  { id: 'off', label: 'Off' },
];

const nameOf = (parts: HookTransitionPart[], id: string | null | undefined) =>
  parts.find((part) => part.id === id)?.name ?? id ?? '';

/**
 * Picks the bridge played between a clip's hook and the clip itself.
 *
 * Auto (the default) lets the server choose one that fits the clip's content
 * and hook line; Presets lists the curated mixes; Mix builds one part by part.
 * The recipe at the bottom is always the server's resolution of the current
 * choice, so what it shows is exactly what the export renders.
 */
export const HookTransitionPanel: React.FC<HookTransitionPanelProps> = ({ clipId, config, onChange }) => {
  const { catalog, error } = useHookTransitionCatalog();
  const [resolved, setResolved] = useState<HookTransitionApplied | null | undefined>(undefined);
  const [resolveError, setResolveError] = useState<string | null>(null);

  const configKey = JSON.stringify(config);
  useEffect(() => {
    if (!clipId) return;
    let active = true;
    // Debounced: sliders and typing fire a change per step.
    const timer = setTimeout(() => {
      hookTransitionApi
        .resolveForClip(clipId, config)
        .then((response) => {
          if (!active) return;
          setResolved(response.transition);
          setResolveError(null);
        })
        .catch((err: Error) => active && setResolveError(err.message));
    }, 300);
    return () => {
      active = false;
      clearTimeout(timer);
    };
    // configKey stands in for config: the object is rebuilt on every change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clipId, configKey]);

  if (error) {
    return <p className="text-xs text-rose-400">{error}</p>;
  }
  if (!catalog) {
    return <p className="text-xs text-neutral-500">Loading hook transitions…</p>;
  }

  const setMode = (mode: HookTransitionMode) => {
    if (mode === config.mode) return;
    if (mode === 'preset') {
      onChange({ mode, preset_id: config.preset_id ?? resolved?.preset_id ?? catalog.default_preset });
    } else if (mode === 'custom') {
      // A mix starts from whatever is showing now, so switching loses nothing.
      onChange({ mode, preset_id: config.preset_id ?? resolved?.preset_id ?? catalog.default_preset });
    } else {
      onChange({ mode });
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-fuchsia-400" />
          Hook Transition
        </h3>
        <p className="text-[11px] text-neutral-400 mt-1">
          The bridge between your hook and the clip: footage, effects, sound, an impact on the cut and an
          on-screen line. Applied when you export.
        </p>
      </div>

      <div className="grid grid-cols-4 gap-1 p-1 rounded-xl bg-neutral-950 border border-neutral-800">
        {MODES.map((mode) => (
          <button
            key={mode.id}
            onClick={() => setMode(mode.id)}
            className={`py-1.5 rounded-lg text-xs font-bold transition-all ${
              config.mode === mode.id ? 'bg-neutral-800 text-fuchsia-300 shadow' : 'text-neutral-400 hover:text-neutral-200'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {config.mode === 'auto' && <AutoSummary resolved={resolved} onCustomize={() => setMode('custom')} />}
      {config.mode === 'preset' && (
        <PresetGallery
          catalog={catalog}
          selected={config.preset_id ?? null}
          onSelect={(presetId) => onChange({ mode: 'preset', preset_id: presetId })}
          onTweak={() => setMode('custom')}
        />
      )}
      {config.mode === 'custom' && <MixBuilder catalog={catalog} config={config} onChange={onChange} />}
      {config.mode === 'off' && (
        <p className="text-xs text-neutral-400 p-3 rounded-xl bg-neutral-950 border border-neutral-800">
          The hook cuts straight into the clip with no bridge.
        </p>
      )}

      {config.mode !== 'off' && (
        <Recipe catalog={catalog} resolved={resolved} error={resolveError} />
      )}
    </div>
  );
};

const AutoSummary: React.FC<{
  resolved: HookTransitionApplied | null | undefined;
  onCustomize: () => void;
}> = ({ resolved, onCustomize }) => (
  <div className="p-3 rounded-xl bg-fuchsia-500/5 border border-fuchsia-500/20 space-y-2">
    <p className="text-xs text-neutral-300 flex items-center gap-1.5">
      <Wand2 className="w-3.5 h-3.5 text-fuchsia-400" />
      Auto picks a transition and bridge line that fit this clip&apos;s content and hook.
    </p>
    {resolved && (
      <button
        onClick={onCustomize}
        className="text-[11px] font-semibold text-fuchsia-300 hover:text-fuchsia-200"
      >
        Customize this pick →
      </button>
    )}
  </div>
);

const PresetGallery: React.FC<{
  catalog: HookTransitionCatalog;
  selected: string | null;
  onSelect: (presetId: string) => void;
  onTweak: () => void;
}> = ({ catalog, selected, onSelect, onTweak }) => {
  const [query, setQuery] = useState('');
  const [group, setGroup] = useState<string>('All');

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return catalog.presets.filter(
      (preset) =>
        (group === 'All' || preset.group === group) &&
        (!needle ||
          preset.name.toLowerCase().includes(needle) ||
          preset.moods.some((mood) => mood.includes(needle)) ||
          preset.group.toLowerCase().includes(needle)),
    );
  }, [catalog.presets, query, group]);

  const shuffle = () => {
    const pool = visible.length ? visible : catalog.presets;
    onSelect(pool[Math.floor(Math.random() * pool.length)].id);
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <label className="flex-1 flex items-center gap-2 px-3 py-2 rounded-xl bg-neutral-950 border border-neutral-800">
          <Search className="w-3.5 h-3.5 text-neutral-500" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={`Search ${catalog.presets.length} presets`}
            className="flex-1 bg-transparent text-xs text-white placeholder:text-neutral-500 outline-none"
          />
        </label>
        <button
          onClick={shuffle}
          title="Pick a random preset"
          className="px-3 rounded-xl bg-neutral-950 border border-neutral-800 text-neutral-300 hover:text-fuchsia-300"
        >
          <Shuffle className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="flex gap-1.5 overflow-x-auto pb-1">
        {['All', ...catalog.groups].map((name) => (
          <button
            key={name}
            onClick={() => setGroup(name)}
            className={`px-2.5 py-1 rounded-full text-[11px] font-semibold whitespace-nowrap border transition-colors ${
              group === name
                ? 'bg-fuchsia-500/15 border-fuchsia-400/50 text-fuchsia-200'
                : 'bg-neutral-950 border-neutral-800 text-neutral-400 hover:text-neutral-200'
            }`}
          >
            {name}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-2 max-h-80 overflow-y-auto pr-1">
        {visible.map((preset) => {
          const active = preset.id === selected;
          return (
            <button
              key={preset.id}
              onClick={() => onSelect(preset.id)}
              className={`text-left p-2.5 rounded-xl border transition-all ${
                active
                  ? 'bg-neutral-800 border-fuchsia-400 ring-1 ring-fuchsia-400/30'
                  : 'bg-neutral-950 border-neutral-800 hover:border-neutral-700'
              }`}
            >
              <span className="flex items-center justify-between gap-1">
                <span className="text-xs font-bold text-white truncate">{preset.name}</span>
                {active && <Check className="w-3.5 h-3.5 text-fuchsia-300 shrink-0" />}
              </span>
              <span className="block text-[10px] text-neutral-500 mt-0.5">{preset.group}</span>
              <span className="block text-[10px] text-neutral-400 mt-1 leading-snug">
                {[nameOf(catalog.sources, preset.source), ...preset.effects.map((e) => nameOf(catalog.effects, e))]
                  .filter(Boolean)
                  .join(' + ')}
                {' · '}
                {nameOf(catalog.sounds, preset.sound)}
              </span>
            </button>
          );
        })}
        {visible.length === 0 && (
          <p className="col-span-2 text-xs text-neutral-500 py-4 text-center">No presets match.</p>
        )}
      </div>

      {selected && (
        <button onClick={onTweak} className="text-[11px] font-semibold text-fuchsia-300 hover:text-fuchsia-200">
          Tweak this preset in Mix →
        </button>
      )}
    </div>
  );
};

const MixBuilder: React.FC<{
  catalog: HookTransitionCatalog;
  config: HookTransitionConfig;
  onChange: (config: HookTransitionConfig) => void;
}> = ({ catalog, config, onChange }) => {
  const base = catalog.presets.find((preset) => preset.id === config.preset_id) ?? CUSTOM_BASE;
  const value = {
    source: config.source ?? base.source,
    effects: config.effects ?? base.effects,
    sound: config.sound ?? base.sound,
    impact: config.impact ?? base.impact,
    impactSound: config.impact_sound !== undefined ? config.impact_sound ?? 'none' : base.impact_sound ?? 'none',
    textChoice: config.custom_text != null ? 'custom' : config.text_id ?? base.text ?? 'none',
    textStyle: config.text_style ?? base.text_style,
    duration: config.duration ?? base.duration,
  };
  const set = (patch: Partial<HookTransitionConfig>) => onChange({ ...config, mode: 'custom', ...patch });
  const framing = new Set(catalog.limits.framing_effects);

  const toggleEffect = (id: string) => {
    const on = value.effects.includes(id);
    let next = on ? value.effects.filter((effect) => effect !== id) : [...value.effects, id];
    // One framing effect at a time: picking a new one replaces the old.
    if (!on && framing.has(id)) next = next.filter((effect) => effect === id || !framing.has(effect));
    if (next.length > catalog.limits.max_effects) return;
    set({ effects: next });
  };

  return (
    <div className="space-y-4">
      <Field label="Start from">
        <select
          value={config.preset_id ?? ''}
          onChange={(event) => onChange({ mode: 'custom', preset_id: event.target.value || null, source: event.target.value ? null : base.source })}
          className="w-full px-3 py-2 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-white"
        >
          <option value="">Blank mix</option>
          {catalog.groups.map((group) => (
            <optgroup key={group} label={group}>
              {catalog.presets.filter((preset) => preset.group === group).map((preset) => (
                <option key={preset.id} value={preset.id}>{preset.name}</option>
              ))}
            </optgroup>
          ))}
        </select>
      </Field>

      <Field label="Gap footage">
        <ChipGrid parts={catalog.sources} isOn={(id) => id === value.source} onToggle={(id) => set({ source: id })} />
      </Field>

      <Field label={`Effects (${value.effects.length}/${catalog.limits.max_effects}) — one zoom/motion at a time`}>
        <ChipGrid parts={catalog.effects} isOn={(id) => value.effects.includes(id)} onToggle={toggleEffect} />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Gap sound">
          <PartSelect parts={catalog.sounds} value={value.sound} onChange={(id) => set({ sound: id })} />
        </Field>
        <Field label="Impact on the cut">
          <PartSelect parts={catalog.impacts} value={value.impact} onChange={(id) => set({ impact: id })} />
        </Field>
      </div>

      <Field label="Impact sound">
        <PartSelect
          parts={[{ id: 'none', name: 'None', description: '' }, ...catalog.impact_sounds]}
          value={value.impactSound}
          onChange={(id) => set({ impact_sound: id })}
        />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Bridge text">
          <select
            value={value.textChoice}
            onChange={(event) => {
              const choice = event.target.value;
              if (choice === 'custom') set({ custom_text: config.custom_text ?? '' });
              else set({ text_id: choice, custom_text: null });
            }}
            className="w-full px-3 py-2 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-white"
          >
            <option value="auto">Auto — match the hook</option>
            <option value="none">No text</option>
            <option value="custom">Write my own…</option>
            {catalog.phrases.map((phrase) => (
              <option key={phrase.id} value={phrase.id}>{phrase.text}</option>
            ))}
          </select>
        </Field>
        <Field label="Text style">
          <PartSelect parts={catalog.text_styles} value={value.textStyle} onChange={(id) => set({ text_style: id })} />
        </Field>
      </div>

      {value.textChoice === 'custom' && (
        <input
          value={config.custom_text ?? ''}
          maxLength={60}
          onChange={(event) => set({ custom_text: event.target.value })}
          placeholder="e.g. Part 2 is crazier"
          className="w-full px-3 py-2 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-white placeholder:text-neutral-500"
        />
      )}

      <Field label={`Bridge length: ${value.duration.toFixed(1)}s`}>
        <input
          type="range"
          min={catalog.limits.min_duration}
          max={catalog.limits.max_duration}
          step={0.1}
          value={value.duration}
          onChange={(event) => set({ duration: Number(event.target.value) })}
          className="w-full accent-fuchsia-400"
        />
      </Field>
    </div>
  );
};

const Field: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div>
    <span className="text-[11px] text-neutral-400 block mb-1.5">{label}</span>
    {children}
  </div>
);

const PartSelect: React.FC<{
  parts: HookTransitionPart[];
  value: string;
  onChange: (id: string) => void;
}> = ({ parts, value, onChange }) => (
  <select
    value={value}
    onChange={(event) => onChange(event.target.value)}
    className="w-full px-3 py-2 rounded-xl bg-neutral-950 border border-neutral-800 text-xs text-white"
  >
    {parts.map((part) => (
      <option key={part.id} value={part.id} title={part.description}>{part.name}</option>
    ))}
  </select>
);

const ChipGrid: React.FC<{
  parts: HookTransitionPart[];
  isOn: (id: string) => boolean;
  onToggle: (id: string) => void;
}> = ({ parts, isOn, onToggle }) => (
  <div className="flex flex-wrap gap-1.5">
    {parts.map((part) => (
      <button
        key={part.id}
        onClick={() => onToggle(part.id)}
        title={part.description}
        className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border transition-colors ${
          isOn(part.id)
            ? 'bg-fuchsia-500/15 border-fuchsia-400/60 text-fuchsia-200'
            : 'bg-neutral-950 border-neutral-800 text-neutral-400 hover:text-neutral-200'
        }`}
      >
        {part.name}
      </button>
    ))}
  </div>
);

/** What will render, as the server resolved it: hook → bridge → impact → clip. */
const Recipe: React.FC<{
  catalog: HookTransitionCatalog;
  resolved: HookTransitionApplied | null | undefined;
  error: string | null;
}> = ({ catalog, resolved, error }) => {
  if (error) return <p className="text-[11px] text-rose-400">{error}</p>;
  if (resolved === undefined) return null;
  if (resolved === null) {
    return (
      <p className="text-[11px] text-neutral-400 p-3 rounded-xl bg-neutral-950 border border-neutral-800">
        This clip has no hook teaser, so it plays without a bridge.
      </p>
    );
  }
  const preset = catalog.presets.find((item) => item.id === resolved.preset_id);
  const look = [nameOf(catalog.sources, resolved.source), ...resolved.effects.map((e) => nameOf(catalog.effects, e))];
  return (
    <div className="p-3 rounded-xl bg-neutral-950 border border-neutral-800 space-y-2">
      <p className="text-[11px] text-neutral-500">
        Renders as{preset ? <> <span className="text-neutral-300 font-semibold">{preset.name}</span></> : null}
      </p>
      <div className="flex items-stretch gap-1 text-[10px] font-semibold">
        <span className="px-2 py-1.5 rounded-lg bg-neutral-800 text-neutral-300">Hook</span>
        <span className="flex-1 px-2 py-1.5 rounded-lg bg-fuchsia-500/15 text-fuchsia-200 leading-snug">
          {look.join(' + ')} · {nameOf(catalog.sounds, resolved.sound)} · {resolved.duration.toFixed(1)}s
          {resolved.text && <span className="block text-white">“{resolved.text}”</span>}
        </span>
        {resolved.impact !== 'none' && (
          <span className="px-2 py-1.5 rounded-lg bg-amber-500/15 text-amber-200">
            {nameOf(catalog.impacts, resolved.impact)}
            {resolved.impact_sound && ` + ${nameOf(catalog.impact_sounds, resolved.impact_sound)}`}
          </span>
        )}
        <span className="px-2 py-1.5 rounded-lg bg-neutral-800 text-neutral-300">Clip</span>
      </div>
    </div>
  );
};
