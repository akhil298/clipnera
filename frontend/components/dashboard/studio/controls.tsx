"use client";
import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Plus } from 'lucide-react';

/** One folding block of an inspector panel. */
export function Section({
  title,
  aside,
  defaultOpen = true,
  children,
}: {
  title: string;
  aside?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="px-4 py-3 border-b border-neutral-800/70 last:border-b-0 space-y-2.5">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="flex flex-1 min-w-0 items-center gap-1.5 text-left text-[12.5px] font-bold text-white"
        >
          {open ? (
            <ChevronDown className="w-3.5 h-3.5 text-neutral-500" aria-hidden />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-neutral-500" aria-hidden />
          )}
          <span className="truncate">{title}</span>
        </button>
        {aside}
      </div>
      {open && children}
    </section>
  );
}

/** Labelled range slider with its value readout. */
export function RangeField({
  label,
  value,
  display,
  min,
  max,
  step = 1,
  onChange,
}: {
  label: string;
  value: number;
  display: string;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="flex items-center justify-between text-xs text-neutral-400">
        {label}
        <span className="font-mono text-[11.5px] text-neutral-200 tabular-nums">{display}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
      />
    </label>
  );
}

export function Switch({
  checked,
  onChange,
  label,
  disabled = false,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative w-8 h-[18px] shrink-0 rounded-full transition-colors disabled:opacity-40 ${checked ? 'bg-amber-500' : 'bg-neutral-700'}`}
    >
      <span
        className={`absolute top-0.5 w-3.5 h-3.5 rounded-full bg-white transition-all ${checked ? 'left-4' : 'left-0.5'}`}
      />
    </button>
  );
}

export function Chip({
  active,
  onClick,
  children,
  title,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      title={title}
      className={`h-[30px] px-3 rounded-[9px] border text-xs font-semibold whitespace-nowrap inline-flex items-center gap-1.5 transition-colors ${
        active
          ? 'border-amber-400 text-amber-300 bg-amber-500/10'
          : 'border-neutral-800 bg-neutral-900 text-neutral-400 hover:text-neutral-200'
      }`}
    >
      {children}
    </button>
  );
}

/** Quick colour picks plus a custom colour. */
export function ColorSwatches({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  const custom = !options.some((c) => c.toLowerCase() === value.toLowerCase());
  return (
    <div className="flex items-center gap-2">
      <span className="flex-1 text-xs text-neutral-400">{label}</span>
      <div className="flex items-center gap-1.5" role="group" aria-label={label}>
        {options.map((colour) => {
          const on = colour.toLowerCase() === value.toLowerCase();
          return (
            <button
              key={colour}
              type="button"
              onClick={() => onChange(colour)}
              aria-pressed={on}
              aria-label={colour}
              className={`w-[22px] h-[22px] rounded-[7px] border-2 ${on ? 'border-white ring-2 ring-white/20' : 'border-transparent'}`}
              style={{ backgroundColor: colour }}
            />
          );
        })}
        <label
          className={`relative w-[22px] h-[22px] rounded-[7px] border-2 flex items-center justify-center cursor-pointer overflow-hidden ${
            custom ? 'border-white ring-2 ring-white/20' : 'border-dashed border-neutral-600 text-neutral-500'
          }`}
          style={custom ? { backgroundColor: value } : undefined}
          title="Custom colour"
        >
          {!custom && <Plus className="w-3 h-3" aria-hidden />}
          <input
            type="color"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="absolute inset-0 opacity-0 cursor-pointer"
            aria-label={`${label}: custom colour`}
          />
        </label>
      </div>
    </div>
  );
}

/** Small tinted note under a control. */
export function Note({ tone = 'info', icon, children }: { tone?: 'info' | 'ok' | 'warn'; icon: React.ReactNode; children: React.ReactNode }) {
  const colour = tone === 'ok' ? 'text-neutral-400 [&>svg]:text-emerald-400' : tone === 'warn' ? 'text-rose-300 [&>svg]:text-rose-400' : 'text-neutral-400';
  return <p className={`flex items-start gap-1.5 text-[11.5px] leading-snug [&>svg]:w-3.5 [&>svg]:h-3.5 [&>svg]:mt-px [&>svg]:shrink-0 ${colour}`}>{icon}{children}</p>;
}
