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
  return <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">{message}</div>;
}

export function StatTile({ label, value, hint, href }: { label: string; value: string; hint?: string; href?: string }) {
  const body = (
    <div className="p-4 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-1 h-full">
      <p className="text-[11px] font-bold text-neutral-400">{label}</p>
      <p className="text-2xl font-bold text-white font-mono">{value}</p>
      {hint && <p className="text-[11px] text-neutral-500">{hint}</p>}
    </div>
  );
  return href ? (
    <Link href={href} className="block hover:opacity-90">
      {body}
    </Link>
  ) : (
    body
  );
}

export function RangeTabs({ value, onChange }: { value: number; onChange: (days: number) => void }) {
  return (
    <div className="flex gap-1 rounded-xl border border-neutral-800 p-1">
      {ADMIN_RANGES.map((range) => (
        <button
          key={range}
          type="button"
          onClick={() => onChange(range)}
          className={`px-3 py-1 rounded-lg text-xs font-bold ${value === range ? 'bg-amber-400 text-black' : 'text-neutral-400 hover:text-white'}`}
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
    <div className="overflow-x-auto rounded-2xl border border-neutral-800 bg-neutral-900/90">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] text-neutral-400 border-b border-neutral-800">
            {head.map((h, i) => (
              <th key={h} className={`px-4 py-2 font-bold whitespace-nowrap ${i > 0 ? 'text-right' : ''}`}>{h}</th>
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
                <td key={i} className={`px-4 py-2 ${i > 0 ? 'text-right font-mono tabular-nums whitespace-nowrap' : 'text-neutral-200'}`}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
