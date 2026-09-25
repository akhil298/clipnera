'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { PlusCircle, Search } from 'lucide-react';
import { adminCreditsApi, AdminCreditTopupResponse } from '@/lib/api';
import { formatDateTime } from '@/lib/utils/payments';
import { AdminLayout } from './AdminLayout';

const PAGE_SIZE = 50;
const INPUT_CLASS =
  'w-full px-3 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:border-amber-500/60';

export function AdminCreditsView() {
  const [email, setEmail] = useState('');
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [entries, setEntries] = useState<AdminCreditTopupResponse[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
        const page = await adminCreditsApi.list({ q: query || undefined, limit: PAGE_SIZE, offset });
        setEntries((prev) => (offset === 0 ? page : [...prev, ...page]));
        setHasMore(page.length === PAGE_SIZE);
      } catch (err: any) {
        setError(err.message || 'Could not load top-ups');
      } finally {
        setLoading(false);
      }
    },
    [query],
  );

  useEffect(() => {
    load(0);
  }, [load]);

  const minutes = Number(amount);
  const canSubmit =
    !submitting && email.trim() !== '' && Number.isInteger(minutes) && minutes > 0 && reason.trim().length >= 3;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    if (!window.confirm(`Add ${minutes} credit minutes to ${email.trim()}?`)) return;

    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const entry = await adminCreditsApi.topup({ user_email: email.trim(), amount: minutes, reason: reason.trim() });
      setNotice(`Added ${entry.amount} min to ${entry.user_email}. New balance: ${entry.balance_after} min.`);
      setEmail('');
      setAmount('');
      setReason('');
      load(0);
    } catch (err: any) {
      setError(err.message || 'Top-up failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AdminLayout title="Credits" subtitle="Add credit minutes to a user by hand. Every top-up is logged with who made it.">
      <form
        onSubmit={submit}
        className="p-4 rounded-2xl bg-neutral-900/90 border border-neutral-800 grid gap-3 sm:grid-cols-[2fr_1fr_3fr_auto] items-end"
      >
        <label className="space-y-1">
          <span className="text-[11px] font-bold text-neutral-400">User email</span>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="user@example.com" className={INPUT_CLASS} />
        </label>
        <label className="space-y-1">
          <span className="text-[11px] font-bold text-neutral-400">Minutes</span>
          <input type="number" min={1} step={1} value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="100" className={INPUT_CLASS} />
        </label>
        <label className="space-y-1">
          <span className="text-[11px] font-bold text-neutral-400">Reason</span>
          <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={255} placeholder="Refund for failed render" className={INPUT_CLASS} />
        </label>
        <button
          type="submit"
          disabled={!canSubmit}
          className="px-4 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-xs transition-colors disabled:opacity-50 flex items-center justify-center gap-1"
        >
          <PlusCircle className="w-3.5 h-3.5" />
          Add credits
        </button>
      </form>

      {notice && (
        <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm">{notice}</div>
      )}
      {error && <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">{error}</div>}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-bold text-white">Top-up history</h2>
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-neutral-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search user"
            className="w-full pl-9 pr-3 py-2.5 rounded-xl bg-neutral-900 border border-neutral-800 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:border-amber-500/60"
          />
        </div>
      </div>

      {!loading && entries.length === 0 && <p className="text-sm text-neutral-400 py-12 text-center">No top-ups yet.</p>}

      {entries.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-neutral-800">
          <table className="w-full text-sm">
            <thead className="bg-neutral-900 text-[11px] text-neutral-400 text-left">
              <tr>
                <th className="px-4 py-2 font-bold">When</th>
                <th className="px-4 py-2 font-bold">User</th>
                <th className="px-4 py-2 font-bold text-right">Minutes</th>
                <th className="px-4 py-2 font-bold text-right">Balance after</th>
                <th className="px-4 py-2 font-bold">Reason</th>
                <th className="px-4 py-2 font-bold">Added by</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800">
              {entries.map((entry) => (
                <tr key={entry.id} className="bg-neutral-950">
                  <td className="px-4 py-2 text-xs text-neutral-400 whitespace-nowrap">{formatDateTime(entry.created_at)}</td>
                  <td className="px-4 py-2">
                    <p className="text-white text-xs font-bold">{entry.user_name || entry.user_email}</p>
                    <p className="text-[11px] text-neutral-500">{entry.user_email}</p>
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-emerald-400">+{entry.amount}</td>
                  <td className="px-4 py-2 text-right font-mono text-neutral-300">{entry.balance_after}</td>
                  <td className="px-4 py-2 text-xs text-neutral-300">{entry.reason}</td>
                  <td className="px-4 py-2 text-xs text-neutral-400">{entry.created_by_email ?? 'Deleted admin'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {loading && (
        <div className="flex justify-center py-6">
          <div className="w-6 h-6 border-2 border-neutral-700 border-t-amber-400 rounded-full animate-spin" />
        </div>
      )}

      {hasMore && !loading && (
        <div className="flex justify-center">
          <button onClick={() => load(entries.length)} className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-xs font-bold text-white">
            Load more
          </button>
        </div>
      )}
    </AdminLayout>
  );
}
