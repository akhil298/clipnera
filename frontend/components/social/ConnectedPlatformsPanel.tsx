'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Loader2, RefreshCw } from 'lucide-react';
import {
  socialApi,
  type ConnectedAccountResponse,
  type SocialConnectionsResponse,
  type SocialPlatform,
} from '@/lib/api';
import { formatDate } from '@/lib/utils/dates';
import { useFeatureFlags } from '@/hooks/useFeatureFlags';
import { PLATFORM_ORDER, PLATFORM_STYLE, formatAudience } from './platforms';

interface PendingDisconnect {
  account: ConnectedAccountResponse;
  pendingPosts: number;
}

/** Settings → Social accounts: connect, reconnect and disconnect publishing
 * platforms. Tokens never reach the browser; connecting redirects to the
 * platform and back to /dashboard/connect/<platform>. */
export function ConnectedPlatformsPanel() {
  const [data, setData] = useState<SocialConnectionsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [pendingDisconnect, setPendingDisconnect] = useState<PendingDisconnect | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await socialApi.getConnections());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load connected accounts');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const connect = async (platform: SocialPlatform) => {
    setBusy(platform);
    setError(null);
    try {
      const { authorize_url } = await socialApi.startConnect(platform);
      window.location.assign(authorize_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start connecting');
      setBusy(null);
    }
  };

  const askDisconnect = async (account: ConnectedAccountResponse) => {
    setBusy(account.id);
    try {
      const preview = await socialApi.disconnectPreview(account.id);
      setPendingDisconnect({ account, pendingPosts: preview.pending_posts });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not check scheduled posts');
    } finally {
      setBusy(null);
    }
  };

  const confirmDisconnect = async () => {
    if (!pendingDisconnect) return;
    setBusy(pendingDisconnect.account.id);
    try {
      await socialApi.disconnect(pendingDisconnect.account.id);
      setPendingDisconnect(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not disconnect');
    } finally {
      setBusy(null);
    }
  };

  const accountsFor = (platform: SocialPlatform) => data?.accounts.filter((a) => a.platform === platform) ?? [];
  const atLimit = data ? data.accounts.length >= data.max_accounts : true;

  return (
    <div className="p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-5 shadow-xl">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-bold text-white">Connected Publishing Platforms</h3>
          <p className="text-xs text-neutral-400 mt-0.5">
            Authorize your creator profiles for 1-click publishing and scheduling.
          </p>
        </div>
        {data && (
          <span className="text-[11px] text-neutral-400 font-mono">
            {data.accounts.length}/{data.max_accounts} accounts
          </span>
        )}
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/25 text-xs text-rose-300">{error}</div>
      )}

      {!data && !error && (
        <div className="flex items-center gap-2 text-xs text-neutral-400">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading accounts…
        </div>
      )}

      {data && (
        <div className="grid sm:grid-cols-2 gap-4">
          {PLATFORM_ORDER.map((platform) => {
            const info = data.platforms.find((p) => p.platform === platform);
            const accounts = accountsFor(platform);
            const style = PLATFORM_STYLE[platform];
            if (!info || (!info.available && accounts.length === 0)) return null;
            const locked = !info.allowed_by_plan;
            return (
              <div key={platform} className="p-4 rounded-xl bg-neutral-950 border border-neutral-800 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className={`w-2.5 h-2.5 rounded-full bg-gradient-to-r ${style.color}`} />
                    <h4 className="text-xs font-bold text-white">{style.name}</h4>
                  </div>
                  {accounts.length === 0 && (
                    <button
                      onClick={() => connect(platform)}
                      disabled={busy !== null || locked || atLimit || !info.available}
                      title={locked ? 'Available on Pro' : atLimit ? 'Account limit reached for your plan' : undefined}
                      className="px-3 py-1.5 rounded-lg text-xs font-bold transition-all bg-gradient-to-r from-amber-500 to-rose-500 text-neutral-950 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      {busy === platform ? 'Redirecting…' : locked ? 'Pro only' : 'Connect Account'}
                    </button>
                  )}
                </div>

                {accounts.map((account) => (
                  <AccountRow
                    key={account.id}
                    account={account}
                    busy={busy === account.id}
                    disabled={busy !== null}
                    onReconnect={() => connect(platform)}
                    onDisconnect={() => askDisconnect(account)}
                  />
                ))}

                {info.pending_review_note && (
                  <p className="text-[10px] text-amber-300/80 leading-snug">{info.pending_review_note}</p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {pendingDisconnect && (
        <div className="p-4 rounded-xl bg-neutral-950 border border-rose-500/30 space-y-3">
          <p className="text-xs text-neutral-200">
            Disconnect <b>{pendingDisconnect.account.handle || pendingDisconnect.account.display_name}</b>?{' '}
            {pendingDisconnect.pendingPosts > 0
              ? `${pendingDisconnect.pendingPosts} scheduled post${pendingDisconnect.pendingPosts === 1 ? '' : 's'} will be cancelled.`
              : 'No scheduled posts will be affected.'}{' '}
            Clipnera&apos;s access will be revoked and its stored tokens deleted.
          </p>
          <div className="flex gap-2">
            <button
              onClick={confirmDisconnect}
              disabled={busy !== null}
              className="px-3 py-1.5 rounded-lg text-xs font-bold bg-rose-500 hover:bg-rose-400 text-white disabled:opacity-50"
            >
              {busy ? 'Disconnecting…' : 'Disconnect'}
            </button>
            <button
              onClick={() => setPendingDisconnect(null)}
              className="px-3 py-1.5 rounded-lg text-xs font-bold bg-neutral-800 text-neutral-300 border border-neutral-700"
            >
              Keep connected
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function AccountRow({
  account,
  busy,
  disabled,
  onReconnect,
  onDisconnect,
}: {
  account: ConnectedAccountResponse;
  busy: boolean;
  disabled: boolean;
  onReconnect: () => void;
  onDisconnect: () => void;
}) {
  const needsReconnect = account.status === 'needs_reconnect';
  const disconnecting = account.status === 'disconnecting';
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          {account.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={account.avatar_url} alt="" className="w-7 h-7 rounded-full object-cover" referrerPolicy="no-referrer" />
          ) : (
            <span className="w-7 h-7 rounded-full bg-neutral-800" />
          )}
          <div className="min-w-0">
            <p className="text-[11px] text-neutral-200 font-semibold truncate">
              {account.handle || account.display_name}
            </p>
            <span
              className="text-[10px] text-emerald-400 font-mono"
              title={account.follower_count_updated_at ? `Updated ${formatDate(account.follower_count_updated_at)}` : undefined}
            >
              {formatAudience(account.follower_count)} Audience
            </span>
          </div>
        </div>
        <div className="flex gap-1.5 shrink-0">
          {needsReconnect && (
            <button
              onClick={onReconnect}
              disabled={disabled}
              className="px-2.5 py-1.5 rounded-lg text-xs font-bold bg-amber-500 hover:bg-amber-400 text-neutral-950 flex items-center gap-1 disabled:opacity-50"
            >
              <RefreshCw className="w-3 h-3" /> Reconnect
            </button>
          )}
          <button
            onClick={onDisconnect}
            disabled={disabled || disconnecting}
            className="px-3 py-1.5 rounded-lg text-xs font-bold transition-all bg-neutral-800 text-neutral-300 hover:text-rose-400 hover:bg-neutral-800/80 border border-neutral-700 disabled:opacity-50"
          >
            {busy ? '…' : disconnecting ? 'Disconnecting…' : 'Disconnect'}
          </button>
        </div>
      </div>
      {needsReconnect && (
        <p className="flex items-start gap-1.5 text-[10px] text-amber-300 leading-snug">
          <AlertTriangle className="w-3 h-3 mt-px shrink-0" />
          {account.status_reason || 'Access expired. Reconnect to keep publishing.'}
        </p>
      )}
    </div>
  );
}

/** Show the Social accounts tab while the feature is on, and afterwards for as
 * long as the user still has accounts connected, so turning the feature off
 * never stops anyone from disconnecting. */
export function useSocialTabVisible(): boolean {
  const { flags, isLoading } = useFeatureFlags();
  const [hasAccounts, setHasAccounts] = useState(false);

  useEffect(() => {
    if (isLoading || flags.social_publishing) return;
    let active = true;
    socialApi
      .getConnections()
      .then((res) => active && setHasAccounts(res.accounts.length > 0))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [isLoading, flags.social_publishing]);

  return flags.social_publishing || hasAccounts;
}
