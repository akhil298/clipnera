'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { adminBrollApi, BrollAssetResponse, BrollAssetStatus } from '@/lib/api';
import { AdminLayout } from './AdminLayout';

const PAGE_SIZE = 40;
const STATUSES: (BrollAssetStatus | '')[] = ['', 'live', 'blocked', 'taken_down', 'failed'];

const STATUS_STYLE: Record<BrollAssetStatus, string> = {
  live: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20',
  ingesting: 'bg-sky-500/10 text-sky-300 border-sky-500/20',
  blocked: 'bg-amber-500/10 text-amber-300 border-amber-500/20',
  taken_down: 'bg-rose-500/10 text-rose-300 border-rose-500/20',
  failed: 'bg-neutral-800 text-neutral-400 border-neutral-700',
};

function AssetCard({ asset, onStatus }: { asset: BrollAssetResponse; onStatus: (status: 'live' | 'blocked' | 'taken_down') => void }) {
  return (
    <div className="rounded-2xl bg-neutral-900/90 border border-neutral-800 overflow-hidden flex flex-col">
      <div className="relative aspect-[9/16] bg-neutral-950">
        {asset.proxy_url ? (
          <video src={asset.proxy_url} poster={asset.thumb_url ?? undefined} muted loop playsInline preload="none"
            onMouseEnter={(e) => e.currentTarget.play().catch(() => undefined)}
            onMouseLeave={(e) => e.currentTarget.pause()}
            className="w-full h-full object-cover" />
        ) : null}
        <span className={`absolute top-2 left-2 px-1.5 py-0.5 rounded border text-[10px] font-semibold ${STATUS_STYLE[asset.status]}`}>
          {asset.status.replace('_', ' ')}
        </span>
        <span className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/70 text-[10px] font-mono text-neutral-200">
          {asset.duration_s.toFixed(1)}s
        </span>
      </div>
      <div className="p-3 space-y-1.5 flex-1 flex flex-col">
        <p className="text-xs font-bold text-white line-clamp-2">{asset.title || 'Untitled'}</p>
        <p className="text-[10px] text-neutral-400">
          {asset.source} · {asset.license_code ?? 'no licence'} · {asset.width}×{asset.height}
        </p>
        {asset.attribution_text && <p className="text-[10px] text-neutral-500 line-clamp-2">{asset.attribution_text}</p>}
        {asset.status_reason && <p className="text-[10px] text-rose-300">{asset.status_reason}</p>}
        <div className="mt-auto pt-2 flex gap-1.5">
          {asset.source_url && (
            <a href={asset.source_url} target="_blank" rel="noreferrer" className="px-2 py-1 rounded-lg text-[10px] font-semibold text-neutral-300 border border-neutral-800 hover:border-neutral-600">
              Source
            </a>
          )}
          {asset.status === 'live' ? (
            <>
              <button type="button" onClick={() => onStatus('blocked')} className="px-2 py-1 rounded-lg text-[10px] font-semibold text-amber-300 border border-amber-500/30 hover:bg-amber-500/10">
                Block
              </button>
              <button type="button" onClick={() => onStatus('taken_down')} className="px-2 py-1 rounded-lg text-[10px] font-semibold text-rose-300 border border-rose-500/30 hover:bg-rose-500/10">
                Take down
              </button>
            </>
          ) : (
            <button type="button" onClick={() => onStatus('live')} className="px-2 py-1 rounded-lg text-[10px] font-semibold text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/10">
              Restore
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function AdminBrollView() {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<BrollAssetStatus | ''>('');
  const [offset, setOffset] = useState(0);
  const [assets, setAssets] = useState<BrollAssetResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [ingestTopic, setIngestTopic] = useState('');
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    adminBrollApi
      .listAssets({ q: query || undefined, status: status || undefined, limit: PAGE_SIZE, offset })
      .then((res) => {
        setAssets(res.items);
        setTotal(res.total);
      })
      .catch((err: Error) => setError(err.message || 'Could not load the library'));
  }, [query, status, offset]);

  useEffect(() => {
    const id = setTimeout(load, 300);
    return () => clearTimeout(id);
  }, [load]);

  const changeStatus = async (asset: BrollAssetResponse, next: 'live' | 'blocked' | 'taken_down') => {
    const reason = next === 'live' ? null : window.prompt(`Reason for ${next.replace('_', ' ')}?`) ?? undefined;
    if (reason === undefined) return;
    try {
      const updated = await adminBrollApi.setStatus(asset.id, { status: next, reason });
      setAssets((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update the asset');
    }
  };

  const queueIngest = async (event: React.FormEvent) => {
    event.preventDefault();
    if (ingestTopic.trim().length < 2) return;
    try {
      await adminBrollApi.ingest({ query: ingestTopic.trim(), per_source: 5 });
      setNotice(`Ingest queued for "${ingestTopic.trim()}". New shots appear here as they finish.`);
      setIngestTopic('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not queue the ingest');
    }
  };

  return (
    <AdminLayout title="B-roll library" subtitle="Licensed stock shots used for reels. Users only ever see these inside their own renders.">
      <div className="space-y-4">
        <form onSubmit={queueIngest} className="flex flex-wrap gap-2 p-3 rounded-2xl bg-neutral-900/90 border border-neutral-800">
          <input
            value={ingestTopic}
            onChange={(e) => setIngestTopic(e.target.value)}
            placeholder="Topic to ingest, e.g. city at night"
            className="flex-1 min-w-[200px] px-3 py-2 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-white focus:outline-none focus:border-amber-400"
          />
          <button type="submit" className="px-4 py-2 rounded-lg bg-amber-500/20 text-amber-300 text-xs font-bold border border-amber-500/30 hover:bg-amber-500/30">
            Ingest from stock sources
          </button>
        </form>
        {notice && <p className="text-xs text-emerald-300">{notice}</p>}

        <div className="flex flex-wrap gap-2 items-center">
          <input
            value={query}
            onChange={(e) => {
              setOffset(0);
              setQuery(e.target.value);
            }}
            placeholder="Search the library"
            className="flex-1 min-w-[200px] px-3 py-2 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-white focus:outline-none focus:border-amber-400"
          />
          <select
            value={status}
            onChange={(e) => {
              setOffset(0);
              setStatus(e.target.value as BrollAssetStatus | '');
            }}
            className="px-3 py-2 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-white"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s ? s.replace('_', ' ') : 'All statuses'}</option>
            ))}
          </select>
          <span className="text-xs text-neutral-400 tabular-nums">{total} shots</span>
        </div>

        {error && <p className="text-xs text-rose-400">{error}</p>}

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {assets.map((asset) => (
            <AssetCard key={asset.id} asset={asset} onStatus={(next) => changeStatus(asset, next)} />
          ))}
        </div>
        {assets.length === 0 && !error && <p className="text-xs text-neutral-500 text-center py-8">No shots match.</p>}

        {total > PAGE_SIZE && (
          <div className="flex justify-center gap-2">
            <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              className="px-3 py-1.5 rounded-lg text-xs text-neutral-300 border border-neutral-800 disabled:opacity-40">Previous</button>
            <button type="button" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}
              className="px-3 py-1.5 rounded-lg text-xs text-neutral-300 border border-neutral-800 disabled:opacity-40">Next</button>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
