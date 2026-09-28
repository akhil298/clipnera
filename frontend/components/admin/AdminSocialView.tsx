'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  adminSocialApi,
  type AdminSocialAccountResponse,
  type AdminSocialOverviewResponse,
} from '@/lib/api';
import { formatDate } from '@/lib/utils/dates';
import { PLATFORM_STYLE, formatAudience } from '@/components/social/platforms';
import { AdminLayout } from './AdminLayout';
import { FeatureSwitches } from './FeatureSwitches';

const card = 'p-4 rounded-2xl bg-neutral-900/90 border border-neutral-800';

/** Feature switches, connection and publishing health, and force-disconnect.
 * Nothing here ever shows or returns platform tokens. */
export function AdminSocialView() {
  const [overview, setOverview] = useState<AdminSocialOverviewResponse | null>(null);
  const [accounts, setAccounts] = useState<AdminSocialAccountResponse[]>([]);
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fail = (err: unknown) => setError(err instanceof Error ? err.message : 'Request failed');

  const loadAccounts = useCallback(
    (q: string) => adminSocialApi.listAccounts({ q: q || undefined }).then((res) => setAccounts(res.accounts)).catch(fail),
    [],
  );

  useEffect(() => {
    adminSocialApi.getOverview().then(setOverview).catch(fail);
    void loadAccounts('');
  }, [loadAccounts]);

  const forceDisconnect = async (account: AdminSocialAccountResponse) => {
    const name = account.handle || account.display_name || account.id;
    if (!window.confirm(`Force-disconnect ${name} (${account.user_email})? Their scheduled posts will be cancelled.`)) return;
    setBusy(account.id);
    try {
      await adminSocialApi.forceDisconnect(account.id);
      await loadAccounts(query);
    } catch (err) {
      fail(err);
    } finally {
      setBusy(null);
    }
  };

  const youtubeQuota = overview?.quota.youtube;
  const xQuota = overview?.quota.x;

  return (
    <AdminLayout
      title="Social publishing"
      subtitle="Switch the feature on or off, watch publishing health and disconnect accounts. Tokens are never shown."
    >
      {error && <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">{error}</div>}

      <section className={`${card} space-y-3`}>
        <h2 className="text-sm font-bold text-white">Feature switches</h2>
        <FeatureSwitches show={(key) => key.startsWith('social_publishing')} onError={setError} />
      </section>

      {overview && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {overview.platforms.map((stats) => (
              <div key={stats.platform} className={`${card} space-y-1`}>
                <p className="text-[11px] font-bold text-neutral-400">{PLATFORM_STYLE[stats.platform].name}</p>
                <p className="text-2xl font-bold text-white tabular-nums">{stats.accounts.active ?? 0}</p>
                <p className="text-[11px] text-neutral-400">
                  connected · {stats.accounts.needs_reconnect ?? 0} need reconnect
                </p>
                <p className="text-[11px] text-neutral-400">
                  {overview.window_days}d: {stats.posts.published ?? 0} published, {stats.posts.failed ?? 0} failed
                  {stats.success_rate !== null && ` (${Math.round(stats.success_rate * 100)}% ok)`}
                </p>
              </div>
            ))}
          </div>

          <div className="grid sm:grid-cols-2 gap-3">
            <div className={card}>
              <p className="text-[11px] font-bold text-neutral-400">YouTube uploads today (app-wide)</p>
              <p className="text-lg font-bold text-white tabular-nums">
                {youtubeQuota?.used ?? 0} / {youtubeQuota?.limit ?? 0}
              </p>
            </div>
            <div className={card}>
              <p className="text-[11px] font-bold text-neutral-400">X spend this month</p>
              <p className="text-lg font-bold text-white tabular-nums">
                ${(xQuota?.spent_usd ?? 0).toFixed(2)} / ${(xQuota?.budget_usd ?? 0).toFixed(2)}
              </p>
            </div>
          </div>

          <section className={`${card} space-y-2`}>
            <h2 className="text-sm font-bold text-white">Recent failures</h2>
            {overview.recent_failures.length === 0 && <p className="text-xs text-neutral-400">None.</p>}
            {overview.recent_failures.map((failure) => (
              <div key={failure.post_id} className="text-xs border-t border-neutral-800 pt-2">
                <p className="text-neutral-200">
                  <b>{PLATFORM_STYLE[failure.platform].name}</b> · {failure.account_handle} · {failure.user_email}
                </p>
                <p className="text-rose-300">
                  {failure.error_message} <span className="text-neutral-500 font-mono">({failure.error_code})</span>
                </p>
                <p className="text-neutral-500">
                  {formatDate(failure.failed_at)} · {failure.attempts} attempt{failure.attempts === 1 ? '' : 's'}
                </p>
              </div>
            ))}
          </section>
        </>
      )}

      <section className={`${card} space-y-3`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-bold text-white">Connected accounts</h2>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void loadAccounts(query)}
            placeholder="Search email or handle, then Enter"
            className="px-3 py-1.5 rounded-lg bg-neutral-950 border border-neutral-800 text-xs text-white focus:outline-none focus:border-amber-400"
          />
        </div>
        {accounts.length === 0 && <p className="text-xs text-neutral-400">No connected accounts.</p>}
        {accounts.map((account) => (
          <div key={account.id} className="flex items-center justify-between gap-3 text-xs border-t border-neutral-800 pt-2">
            <div className="min-w-0">
              <p className="text-neutral-200 truncate">
                <b>{PLATFORM_STYLE[account.platform].name}</b> · {account.handle || account.display_name} ·{' '}
                {formatAudience(account.follower_count)}
              </p>
              <p className="text-neutral-500 truncate">
                {account.user_email} · {account.status.replace('_', ' ')} · since {formatDate(account.connected_at)}
              </p>
            </div>
            <button
              onClick={() => forceDisconnect(account)}
              disabled={busy !== null || account.status === 'disconnecting'}
              className="px-3 py-1.5 rounded-lg font-bold bg-neutral-800 text-neutral-300 hover:text-rose-400 border border-neutral-700 disabled:opacity-50 shrink-0"
            >
              {busy === account.id ? 'Disconnecting…' : 'Force disconnect'}
            </button>
          </div>
        ))}
      </section>
    </AdminLayout>
  );
}
