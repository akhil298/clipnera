'use client';

import React, { useEffect, useState } from 'react';
import { adminUsageApi, AdminUsageSummary, ClipQualityReport } from '@/lib/api';
import { AdminLayout } from './AdminLayout';
import { AdminError, AdminSpinner, AdminTable, RangeTabs, StatTile, usd } from './AdminUi';

function tokens(value: number): string {
  return value >= 1_000_000 ? `${(value / 1_000_000).toFixed(2)}M` : value >= 1000 ? `${(value / 1000).toFixed(1)}K` : String(value);
}

function Table({ head, rows }: { head: string[]; rows: React.ReactNode[][] }) {
  return <AdminTable head={head} rows={rows} empty="No AI calls in this period." />;
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
      actions={<RangeTabs value={days} onChange={setDays} />}
    >
      {error && <AdminError message={error} />}
      {!summary && !error && <AdminSpinner />}
      {summary && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
            <StatTile label={`Spend, last ${summary.days} days`} value={usd(summary.cost_usd)} />
            <StatTile label="AI calls" value={summary.calls.toLocaleString()} />
            <StatTile label="Average per video (top videos)" value={usd(perVideo)} />
          </div>

          <section className="space-y-2">
            <h2 className="text-sm font-bold text-white">AI cost per source minute</h2>
            <p className="text-[11px] text-neutral-400">
              What a minute of uploaded video really costs in AI. Credits should earn at least 3x this per minute.
            </p>
            <Table
              head={['Tier', 'Videos', 'Source minutes', 'Per minute']}
              rows={summary.cost_per_minute.map((c) => [
                c.tier === 'pro' ? 'Pro (Claude)' : 'Free (Groq)',
                c.projects.toLocaleString(),
                c.source_minutes.toFixed(1),
                usd(c.cost_per_source_minute_usd),
              ])}
            />
          </section>

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
