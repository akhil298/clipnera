'use client';

import React, { useEffect, useState } from 'react';
import { RefreshCw, Search, Sparkles, Trash2 } from 'lucide-react';
import { AI_SHOT_CREDITS, brollApi, BrollPlacement, BrollPreview } from '@/lib/api';
import { useEntitlements } from '@/hooks/useEntitlements';

function Thumb({ preview, active, onPick }: { preview: BrollPreview; active?: boolean; onPick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onPick}
      disabled={!onPick}
      title={preview.attribution_text ?? preview.title}
      className={`relative w-14 aspect-[9/16] rounded-lg overflow-hidden border shrink-0 ${
        active ? 'border-amber-400' : 'border-neutral-800 hover:border-neutral-500'
      }`}
    >
      {preview.thumb_url && <img src={preview.thumb_url} alt={preview.title} className="w-full h-full object-cover" />}
    </button>
  );
}

function PlacementRow({
  placement, busy, isPro, onSwap, onRemove, onGenerate,
}: {
  placement: BrollPlacement;
  busy: boolean;
  isPro: boolean;
  onSwap: (assetId: string) => void;
  onRemove: () => void;
  onGenerate: () => void;
}) {
  const [query, setQuery] = useState(placement.query);
  const [results, setResults] = useState<BrollPreview[] | null>(null);

  const search = async () => {
    setResults(await brollApi.search(query, placement.end - placement.start).catch(() => []));
  };

  return (
    <div className="p-3 rounded-xl bg-neutral-950 border border-neutral-800 space-y-2">
      <div className="flex items-center justify-between text-[11px]">
        <span className="font-bold text-white">
          {placement.start.toFixed(1)}s–{placement.end.toFixed(1)}s · “{placement.query}”
        </span>
        <button type="button" onClick={onRemove} disabled={busy} className="p-1 text-neutral-500 hover:text-rose-400" title="Remove cutaway">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className="flex gap-1.5 overflow-x-auto">
        {placement.asset && <Thumb preview={placement.asset} active />}
        {placement.alternates.map((alt) => (
          <Thumb key={alt.id} preview={alt} onPick={busy ? undefined : () => onSwap(alt.id)} />
        ))}
      </div>
      <div className="flex gap-1.5">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 px-2 py-1 rounded-lg bg-neutral-900 border border-neutral-800 text-[11px] text-white focus:outline-none focus:border-amber-400"
        />
        <button type="button" onClick={search} className="px-2 py-1 rounded-lg border border-neutral-800 text-neutral-300 hover:text-white" title="Search the library">
          <Search className="w-3.5 h-3.5" />
        </button>
      </div>
      <button type="button" onClick={onGenerate} disabled={busy || !isPro || placement.generating}
        title={isPro ? 'Generate a new shot for this cutaway with AI' : 'AI shots are a Pro feature'}
        className="w-full py-1 rounded-lg border border-violet-500/30 text-[10px] font-semibold text-violet-300 hover:bg-violet-500/10 disabled:opacity-40 flex items-center justify-center gap-1">
        {placement.generating ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
        {placement.generating ? 'Generating AI shot…' : `AI shot · ${AI_SHOT_CREDITS} credits${isPro ? '' : ' (Pro)'}`}
      </button>
      {results && (
        <div className="flex gap-1.5 overflow-x-auto">
          {results.length === 0 && <span className="text-[10px] text-neutral-500">No shots match.</span>}
          {results.map((r) => (
            <Thumb key={r.id} preview={r} onPick={busy ? undefined : () => onSwap(r.id)} />
          ))}
        </div>
      )}
    </div>
  );
}

/** The clip's real cutaways from the server; changes apply on the next export. */
export function ClipBrollPanel({ clipId }: { clipId: string }) {
  const { entitlements } = useEntitlements();
  const [placements, setPlacements] = useState<BrollPlacement[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    brollApi.getClip(clipId).then((res) => setPlacements(res.placements)).catch(() => setPlacements([]));
  }, [clipId]);

  // An AI shot lands in the background; refresh until none is still generating.
  const generating = placements?.some((p) => p.generating) ?? false;
  useEffect(() => {
    if (!generating) return;
    const id = setInterval(() => {
      brollApi.getClip(clipId).then((res) => setPlacements(res.placements)).catch(() => undefined);
    }, 3000);
    return () => clearInterval(id);
  }, [clipId, generating]);

  const generate = async (index: number) => {
    setError(null);
    try {
      setPlacements((await brollApi.generatePlacement(clipId, index)).placements);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the AI shot');
    }
  };

  const update = async (index: number, payload: { asset_id?: string; remove?: boolean }) => {
    setBusy(true);
    setError(null);
    try {
      setPlacements((await brollApi.updatePlacement(clipId, index, payload)).placements);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update the cutaway');
    } finally {
      setBusy(false);
    }
  };

  if (placements === null) {
    return <p className="text-[11px] text-neutral-500 flex items-center gap-1.5"><RefreshCw className="w-3 h-3 animate-spin" /> Loading cutaways…</p>;
  }
  return (
    <div className="space-y-2">
      <p className="text-[11px] text-neutral-400">
        {placements.length
          ? 'Cutaways the AI placed on this clip. Swap or remove any; the next export uses your changes.'
          : 'No cutaways on this clip. Turn on AI B-Roll Cutaways when creating clips to add them.'}
      </p>
      {error && <p className="text-[11px] text-rose-400">{error}</p>}
      {placements.map((p) => (
        <PlacementRow
          key={`${p.index}:${p.asset?.id}`}
          placement={p}
          busy={busy}
          isPro={Boolean(entitlements?.pro_ai_provider)}
          onSwap={(assetId) => update(p.index, { asset_id: assetId })}
          onRemove={() => update(p.index, { remove: true })}
          onGenerate={() => generate(p.index)}
        />
      ))}
    </div>
  );
}
