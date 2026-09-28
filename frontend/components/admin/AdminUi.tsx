'use client';

import React from 'react';
import Link from 'next/link';

/** Day ranges offered by the admin reports. */
export const ADMIN_RANGES = [7, 30, 90];

export function usd(value: number): string {
  return `$${value > 0 && value < 1 ? value.toFixed(4) : value.toFixed(2)}`;
}

export function AdminSpinner() {
  return (
    <div className="flex justify-center py-12">
      <div className="w-6 h-6 border-2 border-neutral-700 border-t-amber-400 rounded-full animate-spin" />
    </div>
  );
}

export function AdminError({ message }: { message: string }) {
  return <div role="alert" className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-200 text-sm">{message}</div>;
}

export function StatTile({
  label,
  value,
  hint,
  href,
  attention = false,
}: {
  label: string;
  value: string;
  hint?: string;
  href?: string;
  /** Something is waiting on an admin, e.g. payments to review. */
  attention?: boolean;
}) {
  const body = (
    <div
      className={`p-4 rounded-2xl border space-y-1 h-full transition-colors ${
        attention ? 'bg-amber-500/[0.06] border-amber-500/40' : 'bg-neutral-900/80 border-neutral-800'
      } ${href ? 'hover:border-neutral-600' : ''}`}
    >
      <p className="text-xs font-medium text-neutral-400">{label}</p>
      <p className={`text-2xl font-bold tabular-nums tracking-tight ${attention ? 'text-amber-300' : 'text-white'}`}>{value}</p>
      {hint && <p className="text-[11.5px] text-neutral-500">{hint}</p>}
    </div>
  );
  return href ? (
    <Link href={href} className="block">
      {body}
    </Link>
  ) : (
    body
  );
}

export function RangeTabs({ value, onChange }: { value: number; onChange: (days: number) => void }) {
  return (
    <div className="inline-flex gap-0.5 rounded-xl border border-neutral-800 bg-neutral-900 p-0.5" role="group" aria-label="Date range">
      {ADMIN_RANGES.map((range) => (
        <button
          key={range}
          type="button"
          onClick={() => onChange(range)}
          aria-pressed={value === range}
          className={`h-8 px-3 rounded-[10px] text-xs font-semibold transition-colors ${value === range ? 'bg-neutral-800 text-white' : 'text-neutral-400 hover:text-white'}`}
        >
          {range} days
        </button>
      ))}
    </div>
  );
}

/** A table whose first column is text and the rest right-aligned figures. */
export function AdminTable({ head, rows, empty }: { head: string[]; rows: React.ReactNode[][]; empty: string }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-neutral-800 bg-neutral-900/80">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wide text-neutral-500 border-b border-neutral-800">
            {head.map((h, i) => (
              <th key={h} className={`px-4 py-2.5 font-semibold whitespace-nowrap ${i > 0 ? 'text-right' : ''}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={head.length} className="px-4 py-6 text-center text-neutral-500 text-xs">{empty}</td>
            </tr>
          )}
          {rows.map((row, r) => (
            <tr key={r} className="border-b border-neutral-800/60 last:border-0">
              {row.map((cell, i) => (
                <td key={i} className={`px-4 py-2.5 ${i > 0 ? 'text-right tabular-nums whitespace-nowrap' : 'text-neutral-200'}`}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
