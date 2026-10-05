'use client';

import { Area, AreaChart, ResponsiveContainer, YAxis } from 'recharts';

import { cx } from '@/lib/design/styles';
import { useReducedMotion } from '@/lib/design/useReducedMotion';

export type SparklineTone = 'accent' | 'neutral' | 'success' | 'danger';

const STROKE: Record<SparklineTone, string> = {
  accent: 'rgb(var(--cn-accent))',
  neutral: 'rgb(var(--cn-fg-secondary))',
  success: 'rgb(var(--cn-success))',
  danger: 'rgb(var(--cn-danger))',
};

export interface SparklineProps {
  /** Values in order, oldest first. */
  data: ReadonlyArray<number>;
  /**
   * What the line says, in words, for screen readers: "Views over 7 days,
   * rising from 120 to 480". The chart itself is an image.
   */
  label: string;
  /** One series, one hue; status tones only when the trend is the status. */
  tone?: SparklineTone;
  /** Fill under the line at low opacity. Default true. */
  area?: boolean;
  /** Height via a class (`h-8` default); width fills the parent. */
  className?: string;
}

/**
 * A word-sized trend line for StatCard and table cells (recharts). No axes,
 * no grid, no legend: the number beside it carries the value. Under reduced
 * motion it draws without animating.
 */
export function Sparkline({ data, label, tone = 'accent', area = true, className }: SparklineProps) {
  const reduced = useReducedMotion();
  const points = data.map((value, index) => ({ index, value }));
  const stroke = STROKE[tone];
  return (
    <div role="img" aria-label={label} className={cx('h-8 w-full min-w-16', className)}>
      {points.length > 1 && (
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
            <YAxis hide domain={['dataMin', 'dataMax']} />
            <Area
              type="monotone"
              dataKey="value"
              stroke={stroke}
              strokeWidth={2}
              fill={stroke}
              fillOpacity={area ? 0.12 : 0}
              dot={false}
              activeDot={false}
              isAnimationActive={!reduced}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
