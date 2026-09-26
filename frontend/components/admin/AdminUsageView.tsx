'use client';

import React, { useEffect, useState } from 'react';
import { adminUsageApi, AdminUsageSummary, ClipQualityReport } from '@/lib/api';
import { AdminLayout } from './AdminLayout';

const RANGES = [7, 30, 90];

function usd(value: number): string {
  return `$${value < 1 ? value.toFixed(4) : value.toFixed(2)}`;
}

function tokens(value: number): string {
  return value >= 1_000_000 ? `${(value / 1_000_000).toFixed(2)}M` : value >= 1000 ? `${(value / 1000).toFixed(1)}K` : String(value);
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-4 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-1 h-full">
      <p className="text-[11px] font-bold text-neutral-400">{label}</p>
      <p className="text-2xl font-bold text-white font-mono">{value}</p>
    </div>
  );
}

function Table({ head, rows }: { head: string[]; rows: React.ReactNode[][] }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-neutral-800 bg-neutral-900/90">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] text-neutral-400 border-b border-neutral-800">
            {head.map((h, i) => (
              <th key={h} className={`px-4 py-2 font-bold ${i > 0 ? 'text-right' : ''}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={head.length} className="px-4 py-6 text-center text-neutral-500 text-xs">No AI calls in this period.</td>
            </tr>
          )}
          {rows.map((row, r) => (
            <tr key={r} className="border-b border-neutral-800/60 last:border-0">
              {row.map((cell, i) => (
                <td key={i} className={`px-4 py-2 ${i > 0 ? 'text-right font-mono tabular-nums' : 'text-neutral-200'}`}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AdminUsageView() {
  const [days, setDays] = useState(30);
  const [summary, setSummary] = useState<AdminUsageSummary | null>(null);
  const [quality, setQuality] = useState<ClipQualityReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSummary(null);
    setError(null);
    adminUsageApi
      .getSummary(days)
      .then(setSummary)
      .catch((err: Error) => setError(err.message || 'Could not load AI usage'));
    // Secondary: the spend view still renders if this one fails.
    adminUsageApi.getClipQuality(days).then(setQuality).catch(() => setQuality(null));
  }, [days]);

  const perVideo = summary && summary.top_projects.length
    ? summary.top_projects.reduce((acc, p) => acc + p.cost_usd, 0) / summary.top_projects.length
    : 0;

  return (
    <AdminLayout
      title="AI usage"
      subtitle="Tokens and dollars spent on AI models, from every call the pipeline makes."
      actions={
        <div className="flex gap-1 rounded-xl border border-neutral-800 p-1">
          {RANGES.map((range) => (
            <button
              key={range}
              type="button"
              onClick={() => setDays(range)}
              className={`px-3 py-1 rounded-lg text-xs font-bold ${days === range ? 'bg-amber-400 text-black' : 'text-neutral-400 hover:text-white'}`}
            >
              {range} days
            </button>
          ))}
        </div>
      }
    >
      {error && <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">{error}</div>}
      {!summary && !error && (
        <div className="flex justify-center py-12">
          <div className="w-6 h-6 border-2 border-neutral-700 border-t-amber-400 rounded-full animate-spin" />
        </div>
      )}
      {summary && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            <StatTile label={`Spend, last ${summary.days} days`} value={usd(summary.cost_usd)} />
            <StatTile label="AI calls" value={summary.calls.toLocaleString()} />
            <StatTile label="Average per video (top videos)" value={usd(perVideo)} />
          </div>

          <section className="space-y-2">
            <h2 className="text-sm font-bold text-white">By model</h2>
            <Table
              head={['Model', 'Calls', 'Input tokens', 'Output tokens', 'Spend']}
              rows={summary.by_model.map((m) => [
                `${m.provider} / ${m.model}`, m.calls.toLocaleString(), tokens(m.input_tokens), tokens(m.output_tokens), usd(m.cost_usd),
              ])}
            />
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-bold text-white">Most expensive videos</h2>
            <Table
              head={['Project', 'User', 'Calls', 'Spend']}
              rows={summary.top_projects.map((p) => [
                <span key="p" className="font-mono text-xs">{p.project_id}</span>,
                <span key="u" className="font-mono text-xs">{p.user_id ?? '—'}</span>,
                p.calls.toLocaleString(),
                usd(p.cost_usd),
              ])}
            />
          </section>

          {quality && (
            <section className="space-y-2">
              <h2 className="text-sm font-bold text-white">Clip quality by director version</h2>
              <p className="text-xs text-neutral-400">Share of clips users exported, edited or published. Compare versions before and after a prompt change.</p>
              <Table
                head={['Version', 'Clips', 'Exported', 'Edited', 'Published']}
                rows={quality.versions.map((v) => [
                  <span key="v" className="font-mono text-xs">{v.director_version}</span>,
                  v.clips.toLocaleString(),
                  `${Math.round(v.exported_share * 100)}%`,
                  `${Math.round(v.edited_share * 100)}%`,
                  `${Math.round(v.published_share * 100)}%`,
                ])}
              />
            </section>
          )}

          <section className="space-y-2">
            <h2 className="text-sm font-bold text-white">By day</h2>
            <Table
              head={['Day', 'Calls', 'Spend']}
              rows={[...summary.by_day].reverse().map((d) => [d.day, d.calls.toLocaleString(), usd(d.cost_usd)])}
            />
          </section>
        </div>
      )}
    </AdminLayout>
  );
}
