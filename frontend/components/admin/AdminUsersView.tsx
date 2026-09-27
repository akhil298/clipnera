'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Crown, Search } from 'lucide-react';
import { adminUsersApi, AdminUserResponse, AdminUserSort } from '@/lib/api';
import { isPaidPlanSlug, planLabel } from '@/hooks/useEntitlements';
import { formatDate, formatDay } from '@/lib/utils/dates';
import { formatAmount, formatDateTime } from '@/lib/utils/payments';
import { AdminLayout } from './AdminLayout';
import { usd } from './AdminUi';

const PAGE_SIZE = 50;
const GRANT_PRESETS = [7, 30, 365];
const SORTS: { value: AdminUserSort; label: string }[] = [
  { value: 'newest', label: 'Newest sign-ups' },
  { value: 'last_active', label: 'Recently active' },
  { value: 'projects', label: 'Most projects' },
  { value: 'ai_cost', label: 'Highest AI cost' },
];

function UserFigures({ user }: { user: AdminUserResponse }) {
  const figures: [string, string][] = [
    ['Last active', user.last_active_on ? formatDay(user.last_active_on) : '—'],
    ['Last login', user.last_login_at ? formatDateTime(user.last_login_at) : '—'],
    ['Projects', user.projects.toLocaleString()],
    ['Clips', user.clips.toLocaleString()],
    ['Credits left', user.credits_left.toLocaleString()],
    ['Paid', formatAmount(user.total_paid, 'INR')],
    ['AI cost', usd(user.ai_cost_usd)],
  ];
  return (
    <dl className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-x-4 gap-y-2">
      {figures.map(([label, value]) => (
        <div key={label}>
          <dt className="text-[10px] font-bold text-neutral-500">{label}</dt>
          <dd className="text-xs font-mono text-neutral-200">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function AdminUsersView() {
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<AdminUserSort>('newest');
  const [users, setUsers] = useState<AdminUserResponse[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [granting, setGranting] = useState<{ id: string; days: string } | null>(null);

  // Debounce search so typing does not fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const load = useCallback(
    async (offset: number) => {
      setLoading(true);
      setError(null);
      try {
        const page = await adminUsersApi.list({ q: query || undefined, limit: PAGE_SIZE, offset, sort });
        setUsers((prev) => (offset === 0 ? page : [...prev, ...page]));
        setHasMore(page.length === PAGE_SIZE);
      } catch (err: any) {
        setError(err.message || 'Could not load users');
      } finally {
        setLoading(false);
      }
    },
    [query, sort],
  );

  useEffect(() => {
    load(0);
  }, [load]);

  const setPlan = async (user: AdminUserResponse, plan: 'pro' | 'free', days?: number) => {
    const prompt =
      plan === 'pro'
        ? `Give ${user.email} ${days} day${days === 1 ? '' : 's'} of Pro? This is added to any Pro time they have.`
        : `Revoke Pro from ${user.email} now? Their credits are capped at the Free allowance.`;
    if (!window.confirm(prompt)) return;

    setBusyId(user.id);
    setError(null);
    try {
      const updated = await adminUsersApi.setPlan(user.id, { plan, days });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      setGranting(null);
    } catch (err: any) {
      setError(err.message || 'Could not change the plan');
    } finally {
      setBusyId(null);
    }
  };

  const grantDays = granting ? Number(granting.days) : 0;
  const grantValid = Number.isInteger(grantDays) && grantDays >= 1 && grantDays <= 3650;

  return (
    <AdminLayout
      title="Users"
      subtitle="Grant Pro for refunds, gifts or testing, or revoke it. Open a user to see everything they have done."
      actions={
        <div className="flex flex-wrap gap-2 w-full sm:w-auto">
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as AdminUserSort)}
          aria-label="Sort users"
          className="px-3 py-2.5 rounded-xl bg-neutral-900 border border-neutral-800 text-sm text-white focus:outline-none focus:border-amber-500/60"
        >
          {SORTS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-neutral-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search email or name"
            className="w-full pl-9 pr-3 py-2.5 rounded-xl bg-neutral-900 border border-neutral-800 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:border-amber-500/60"
          />
        </div>
        </div>
      }
    >
      {error && <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">{error}</div>}
      {!loading && users.length === 0 && <p className="text-sm text-neutral-400 py-12 text-center">No users found.</p>}

      <ul className="space-y-2">
        {users.map((u) => {
          const isPro = isPaidPlanSlug(u.plan);
          return (
            <li key={u.id} className="p-4 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-3">
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex-1 min-w-[12rem]">
                  <p className="text-sm font-bold text-white">
                    {u.name || u.email}
                    {u.role === 'admin' && <span className="ml-2 text-[10px] font-bold text-violet-300">ADMIN</span>}
                  </p>
                  <p className="text-xs text-neutral-400">{u.email}</p>
                  <p className="text-[11px] text-neutral-500">
                    Joined {formatDate(u.created_at)} ·{' '}
                    <Link href={`/admin/users/${u.id}`} className="font-bold text-amber-300 hover:text-amber-200">
                      View activity
                    </Link>
                  </p>
                </div>
                <div className="text-right">
                  <p
                    className={`inline-flex items-center gap-1 text-xs font-bold ${
                      isPro ? 'text-amber-300' : 'text-neutral-300'
                    }`}
                  >
                    {isPro && <Crown className="w-3.5 h-3.5" />}
                    {planLabel(u.plan)}
                  </p>
                  <p className="text-[11px] text-neutral-500">
                    {u.plan_expires_at ? `Until ${formatDate(u.plan_expires_at)}` : 'No expiry'}
                  </p>
                </div>
                <div className="flex gap-2">
                  {isPro && (
                    <button
                      onClick={() => setPlan(u, 'free')}
                      disabled={busyId === u.id}
                      className="px-3 py-2 rounded-xl bg-neutral-800 hover:bg-red-500/20 text-red-300 font-bold text-xs disabled:opacity-50"
                    >
                      Revoke Pro
                    </button>
                  )}
                  <button
                    onClick={() => setGranting({ id: u.id, days: '30' })}
                    disabled={busyId === u.id}
                    className="px-3 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs disabled:opacity-50"
                  >
                    {isPro ? 'Extend Pro' : 'Grant Pro'}
                  </button>
                </div>
              </div>

              <UserFigures user={u} />

              {granting?.id === u.id && (
                <div className="p-3 rounded-xl bg-neutral-950 border border-amber-500/30 flex flex-wrap items-center gap-2">
                  {GRANT_PRESETS.map((days) => (
                    <button
                      key={days}
                      onClick={() => setGranting({ id: u.id, days: String(days) })}
                      className="px-2.5 py-1 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-[11px] text-neutral-200"
                    >
                      {days} days
                    </button>
                  ))}
                  <input
                    type="number"
                    min={1}
                    max={3650}
                    step={1}
                    value={granting.days}
                    onChange={(e) => setGranting({ id: u.id, days: e.target.value })}
                    className="w-24 px-3 py-1.5 rounded-lg bg-neutral-900 border border-neutral-800 text-sm text-white focus:outline-none focus:border-amber-500/60"
                    aria-label="Days of Pro"
                  />
                  <span className="text-xs text-neutral-400">days</span>
                  <div className="flex gap-2 ml-auto">
                    <button onClick={() => setGranting(null)} className="px-3 py-1.5 rounded-lg text-xs text-neutral-300 hover:text-white">
                      Cancel
                    </button>
                    <button
                      onClick={() => setPlan(u, 'pro', grantDays)}
                      disabled={!grantValid || busyId === u.id}
                      className="px-4 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs disabled:opacity-50"
                    >
                      Confirm
                    </button>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {loading && (
        <div className="flex justify-center py-6">
          <div className="w-6 h-6 border-2 border-neutral-700 border-t-amber-400 rounded-full animate-spin" />
        </div>
      )}

      {hasMore && !loading && (
        <div className="flex justify-center">
          <button onClick={() => load(users.length)} className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-xs font-bold text-white">
            Load more
          </button>
        </div>
      )}
    </AdminLayout>
  );
}
