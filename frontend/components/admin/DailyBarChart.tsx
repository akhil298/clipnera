'use client';

import React from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TooltipContentProps } from 'recharts';
import { formatDay } from '@/lib/utils/dates';

// amber-600: inside the dark-mode lightness band and >= 3:1 on neutral-900.
const BAR = '#d97706';
const GRID = '#262626';
const TICK = { fill: '#737373', fontSize: 10 };

export interface DailyPoint {
  /** UTC day, YYYY-MM-DD. */
  day: string;
  value: number;
}

function shortDay(day: string): string {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' });
}

/** One measure per UTC day. One series, so the title names it and there is no legend. */
export function DailyBarChart({
  title,
  total,
  points,
  format,
  wholeNumbers = false,
}: {
  title: string;
  /** The period's headline figure, shown beside the title. */
  total: string;
  points: DailyPoint[];
  format: (value: number) => string;
  /** Counts: keep axis ticks on whole numbers. */
  wholeNumbers?: boolean;
}) {
  const renderTooltip = ({ active, payload, label }: TooltipContentProps) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2 text-xs shadow-lg">
        <p className="text-neutral-400">{formatDay(String(label))}</p>
        <p className="font-bold text-white tabular-nums">{format(Number(payload[0].value))}</p>
      </div>
    );
  };

  return (
    <section className="p-4 rounded-2xl bg-neutral-900/80 border border-neutral-800 space-y-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-xs font-bold text-neutral-300">{title}</h3>
        <span className="text-sm font-bold tabular-nums text-white">{total}</span>
      </div>
      <div className="h-40" role="img" aria-label={`${title} per day: ${total} in total`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={points} margin={{ top: 4, right: 4, bottom: 0, left: -12 }} barCategoryGap={2}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="day" tickFormatter={shortDay} tick={TICK} tickLine={false} axisLine={false} minTickGap={24} />
            <YAxis tick={TICK} tickLine={false} axisLine={false} width={44} tickFormatter={(v: number) => format(v)} allowDecimals={!wholeNumbers} />
            <Tooltip content={renderTooltip} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
            <Bar dataKey="value" fill={BAR} radius={[4, 4, 0, 0]} maxBarSize={24} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
