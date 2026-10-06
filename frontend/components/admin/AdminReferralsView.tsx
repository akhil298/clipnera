'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Search } from 'lucide-react';
import { adminReferralApi } from '@/lib/api';
import { OPEN_REFERRAL_STATUSES, REFERRAL_FAIL_LABELS, REFERRAL_STATUS_LABELS } from '@/lib/referral';
import type { AdminReferralResponse, AdminReferralSettingsResponse, ReferralRules } from '@/lib/types';
import { formatDateTime } from '@/lib/utils/payments';
import { AdminLayout } from './AdminLayout';
import { FeatureSwitches } from './FeatureSwitches';

const PAGE_SIZE = 50;
const INPUT_CLASS =
  'w-full px-3 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:border-amber-500/60';

type Filter = 'all' | 'held' | 'open' | 'ended';
const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'held', label: 'On hold' },
  { id: 'open', label: 'In progress' },
  { id: 'ended', label: 'Ended' },
];

const SETTINGS: { key: keyof ReferralRules; label: string; unit: string }[] = [
  { key: 'referee_pro_credits', label: 'Referred user bonus (on Pro)', unit: 'credits' },
  { key: 'referrer_pro_credits', label: 'Referrer reward: Pro bought', unit: 'credits' },
  { key: 'referrer_video_credits', label: 'Referrer reward: first video', unit: 'credits' },
  { key: 'bonus_expiry_days', label: 'Bonus credits expire after', unit: 'days' },
  { key: 'pro_window_hours', label: 'Time to buy Pro after sign-up', unit: 'hours' },
  { key: 'video_window_hours', label: 'Time to start a video after Pro', unit: 'hours' },
  { key: 'monthly_cap', label: 'Referrals per person per month', unit: 'people' },
  { key: 'min_video_seconds', label: 'Shortest video that counts', unit: 'seconds' },
  { key: 'approval_wait_days', label: 'Longest wait for payment approval', unit: 'days' },
];

function statusTone(row: AdminReferralResponse): string {
  if (OPEN_REFERRAL_STATUSES.includes(row.status)) return 'bg-amber-500/10 text-amber-300';
  if (row.status === 'succeeded') return 'bg-emerald-500/10 text-emerald-400';
  if (row.status === 'partial') return 'bg-neutral-800 text-neutral-300';
  return 'bg-rose-500/10 text-rose-400';
}

function ReferralList({ onError }: { onError: (message: string | null) => void }) {
  const [filter, setFilter] = useState<Filter>('all');
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [rows, setRows] = useState<AdminReferralResponse[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [voiding, setVoiding] = useState<{ id: string; reason: string } | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const load = useCallback(
    async (offset: number) => {
      setLoading(true);
      onError(null);
      try {
        const page = await adminReferralApi.list({
          q: query || undefined,
          review_state: filter === 'held' ? 'held' : undefined,
          limit: PAGE_SIZE,
          offset,
        });
        // In progress / ended are a grouping of statuses, so they filter here.
        const shown = page.filter((row) =>
          filter === 'open' ? OPEN_REFERRAL_STATUSES.includes(row.status)
            : filter === 'ended' ? !OPEN_REFERRAL_STATUSES.includes(row.status)
              : true,
        );
        setRows((prev) => (offset === 0 ? shown : [...prev, ...shown]));
        setHasMore(page.length === PAGE_SIZE);
      } catch (err) {
        onError(err instanceof Error ? err.message : 'Could not load referrals');
      } finally {
        setLoading(false);
      }
    },
    [query, filter, onError],
  );

  useEffect(() => {
    load(0);
  }, [load]);

  const act = async (action: () => Promise<unknown>) => {
    onError(null);
    try {
      await action();
      setVoiding(null);
      load(0);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'That did not work');
    }
  };

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              aria-pressed={filter === f.id}
              onClick={() => setFilter(f.id)}
              className={`px-3 py-1 rounded-full text-xs font-semibold border ${
                filter === f.id ? 'bg-white text-neutral-950 border-white' : 'border-neutral-800 text-neutral-400 hover:text-white'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-neutral-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search email or code" className={`${INPUT_CLASS} pl-9`} aria-label="Search referrals" />
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-neutral-800 bg-neutral-900/90">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider text-neutral-500 border-b border-neutral-800">
              <th className="px-4 py-2.5 font-semibold">Referrer</th>
              <th className="px-4 py-2.5 font-semibold">Referred user</th>
              <th className="px-4 py-2.5 font-semibold">Status</th>
              <th className="px-4 py-2.5 font-semibold">Rewards paid</th>
              <th className="px-4 py-2.5 font-semibold">Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-b border-neutral-800/60 align-top">
                <td className="px-4 py-3 text-neutral-200">
                  {row.referrer_email ?? <span className="text-neutral-500">Deleted account</span>}
                  <div className="font-jetbrains text-[11px] text-neutral-500">{row.code}</div>
                </td>
                <td className="px-4 py-3 text-neutral-200">
                  {row.referee_email ?? <span className="text-neutral-500">Deleted account</span>}
                  <div className="text-[11px] text-neutral-500">Joined {formatDateTime(row.signed_up_at)}</div>
                  {row.flagged_reason && (
                    <div className="mt-1 inline-flex items-center gap-1 text-[11px] text-rose-400">
                      <AlertTriangle className="w-3 h-3" /> {row.flagged_reason}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold ${statusTone(row)}`}>{REFERRAL_STATUS_LABELS[row.status]}</span>
                  {row.fail_reason && <div className="mt-1 text-[11px] text-neutral-500">{REFERRAL_FAIL_LABELS[row.fail_reason]}</div>}
                  {row.review_state === 'held' && <div className="mt-1 text-[11px] text-amber-300">Rewards on hold</div>}
                </td>
                <td className="px-4 py-3 font-jetbrains text-xs text-neutral-300">
                  {row.rewards.length ? row.rewards.map((r) => r.credits).join(' + ') : '—'}
                </td>
                <td className="px-4 py-3">
                  {voiding?.id === row.id ? (
                    <div className="space-y-2 min-w-[220px]">
                      <input
                        autoFocus
                        value={voiding.reason}
                        onChange={(e) => setVoiding({ id: row.id, reason: e.target.value })}
                        placeholder="Why (shown in the ledger)"
                        className={INPUT_CLASS}
                        aria-label="Reason for voiding"
                      />
                      <div className="flex gap-1.5">
                        <button
                          type="button"
                          disabled={voiding.reason.trim().length < 3}
                          onClick={() => act(() => adminReferralApi.void(row.id, { reason: voiding.reason.trim() }))}
                          className="px-2.5 py-1 rounded-lg bg-rose-500 text-white text-xs font-bold disabled:opacity-40"
                        >
                          Void and take back credits
                        </button>
                        <button type="button" onClick={() => setVoiding(null)} className="px-2.5 py-1 rounded-lg text-xs text-neutral-400">
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      {row.review_state === 'held' && row.status !== 'void' && (
                        <button
                          type="button"
                          onClick={() => act(() => adminReferralApi.approve(row.id))}
                          className="px-2.5 py-1 rounded-lg bg-amber-500 text-neutral-950 text-xs font-bold"
                        >
                          Approve
                        </button>
                      )}
                      {row.status !== 'void' && (
                        <button
                          type="button"
                          onClick={() => setVoiding({ id: row.id, reason: '' })}
                          className="px-2.5 py-1 rounded-lg border border-neutral-700 text-xs font-semibold text-neutral-300 hover:text-white"
                        >
                          Void
                        </button>
                      )}
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-neutral-500">No referrals match.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {hasMore && (
        <button type="button" disabled={loading} onClick={() => load(rows.length)} className="text-sm font-semibold text-amber-400">
          {loading ? 'Loading…' : 'Load more'}
        </button>
      )}
    </section>
  );
}

function ProgramSettings({ onError }: { onError: (message: string | null) => void }) {
  const [data, setData] = useState<AdminReferralSettingsResponse | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const apply = (response: AdminReferralSettingsResponse) => {
    setData(response);
    setDraft(Object.fromEntries(SETTINGS.map(({ key }) => [key, String(response.rules[key])])));
  };

  useEffect(() => {
    adminReferralApi.settings().then(apply).catch((err) => onError(err instanceof Error ? err.message : 'Could not load settings'));
  }, [onError]);

  if (!data) return null;
  const changed = SETTINGS.filter(({ key }) => draft[key] !== String(data.rules[key]));
  const valid = SETTINGS.every(({ key }) => /^\d+$/.test(draft[key] ?? ''));

  const save = async () => {
    setSaving(true);
    setNotice(null);
    onError(null);
    try {
      const body = Object.fromEntries(SETTINGS.map(({ key }) => [key, Number(draft[key])])) as unknown as ReferralRules;
      apply(await adminReferralApi.updateSettings(body));
      setNotice('Saved. New referrals use these rules; running ones keep theirs.');
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Could not save settings');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="space-y-4">
      <div className="p-4 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-3">
        <FeatureSwitches show={(key) => key === 'referral_program'} onError={onError} />
        <p className="text-xs text-neutral-500">
          Changes below apply to referrals that start after you save. Referrals already running keep the rules they started with.
        </p>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {SETTINGS.map(({ key, label, unit }) => (
          <label
            key={key}
            className={`p-3 rounded-xl bg-neutral-900/90 border space-y-1.5 ${
              draft[key] !== String(data.rules[key]) ? 'border-amber-500/50' : 'border-neutral-800'
            }`}
          >
            <span className="block text-xs font-semibold text-neutral-400">{label}</span>
            <span className="flex items-center gap-2">
              <input
                type="number"
                min={0}
                value={draft[key] ?? ''}
                onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
                className={`${INPUT_CLASS} tabular-nums`}
              />
              <span className="text-xs text-neutral-500 whitespace-nowrap">{unit}</span>
            </span>
          </label>
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm text-emerald-400">{notice}</span>
        <button
          type="button"
          disabled={!changed.length || !valid || saving}
          onClick={save}
          className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 text-sm font-bold disabled:opacity-40"
        >
          {saving ? 'Saving…' : changed.length ? `Save ${changed.length} change${changed.length > 1 ? 's' : ''}` : 'Save changes'}
        </button>
      </div>
      <div className="space-y-2">
        <h3 className="text-sm font-bold text-white">Change history</h3>
        {data.history.length === 0 ? (
          <p className="text-xs text-neutral-500">Using the default rules; nothing has been changed yet.</p>
        ) : (
          <ul className="space-y-1.5 text-xs text-neutral-400">
            {data.history.map((change) => (
              <li key={change.created_at}>
                <span className="font-jetbrains text-neutral-500">{formatDateTime(change.created_at)}</span>{' '}
                {change.admin_email ?? 'An admin'} changed{' '}
                {Object.entries(change.changes)
                  .map(([key, { from, to }]) => `${SETTINGS.find((s) => s.key === key)?.label ?? key} ${from} → ${to}`)
                  .join(', ')}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

/** Admin: every referral, holds to review, and the program's rules. */
export function AdminReferralsView() {
  const [tab, setTab] = useState<'list' | 'settings'>('list');
  const [error, setError] = useState<string | null>(null);
  return (
    <AdminLayout
      title="Referrals"
      subtitle="Review sign-ups held for a check, void abuse, and set what referrals earn and by when."
    >
      <div className="flex gap-4 border-b border-neutral-800" role="tablist">
        {(['list', 'settings'] as const).map((id) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`pb-2 text-sm font-semibold border-b-2 ${tab === id ? 'border-amber-500 text-white' : 'border-transparent text-neutral-400'}`}
          >
            {id === 'list' ? 'Referrals' : 'Program settings'}
          </button>
        ))}
      </div>
      {error && <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">{error}</div>}
      {tab === 'list' ? <ReferralList onError={setError} /> : <ProgramSettings onError={setError} />}
    </AdminLayout>
  );
}
