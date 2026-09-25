'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft, CheckCircle2, Copy, Search, XCircle } from 'lucide-react';
import { adminPaymentsApi, userApi, AdminPaymentResponse, PaymentStatus } from '@/lib/api';
import { getToken } from '@/lib/auth';
import { formatAmount, formatDateTime } from '@/lib/utils/payments';
import { PaymentStatusBadge } from './PaymentStatusBadge';

const PAGE_SIZE = 50;
const TABS: { id: PaymentStatus | 'all'; label: string }[] = [
  { id: 'pending', label: 'Pending' },
  { id: 'success', label: 'Success' },
  { id: 'rejected', label: 'Rejected' },
  { id: 'all', label: 'All' },
];
const REJECT_PRESETS = ['UTR not found', 'Amount mismatch', 'Screenshot unclear'];

/** Redirects anyone who is not an admin. The API enforces this independently. */
function useAdminGate(): boolean {
  const router = useRouter();
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace('/login');
      return;
    }
    userApi
      .getMe()
      .then((profile) => {
        if (profile.role === 'admin') setAllowed(true);
        else router.replace('/dashboard');
      })
      .catch(() => router.replace('/login'));
  }, [router]);

  return allowed;
}

export function AdminPaymentsView() {
  const allowed = useAdminGate();
  const [tab, setTab] = useState<PaymentStatus | 'all'>('pending');
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [payments, setPayments] = useState<AdminPaymentResponse[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<{ id: string; reason: string } | null>(null);
  const [preview, setPreview] = useState<AdminPaymentResponse | null>(null);

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
        const page = await adminPaymentsApi.list({
          status: tab === 'all' ? undefined : tab,
          q: query || undefined,
          limit: PAGE_SIZE,
          offset,
        });
        setPayments((prev) => (offset === 0 ? page : [...prev, ...page]));
        setHasMore(page.length === PAGE_SIZE);
      } catch (err: any) {
        setError(err.message || 'Could not load payments');
      } finally {
        setLoading(false);
      }
    },
    [tab, query],
  );

  useEffect(() => {
    if (allowed) load(0);
  }, [allowed, load]);

  useEffect(() => {
    if (!preview) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setPreview(null);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [preview]);

  const applyUpdate = (updated: AdminPaymentResponse) => {
    setPayments((prev) =>
      tab === 'all' || tab === updated.status
        ? prev.map((p) => (p.id === updated.id ? updated : p))
        : prev.filter((p) => p.id !== updated.id),
    );
  };

  const runAction = async (id: string, action: () => Promise<AdminPaymentResponse>) => {
    setBusyId(id);
    setError(null);
    try {
      applyUpdate(await action());
      setRejecting(null);
    } catch (err: any) {
      setError(err.message || 'Action failed');
      // Someone else may have resolved it; show the current state.
      load(0);
    } finally {
      setBusyId(null);
    }
  };

  const approve = (p: AdminPaymentResponse) => {
    const confirmed = window.confirm(
      `Approve ${formatAmount(p.amount, p.currency)} from ${p.user_email} (UTR ${p.utr_number})?\n\nThis activates their ${p.plan_name} plan.`,
    );
    if (confirmed) runAction(p.id, () => adminPaymentsApi.approve(p.id));
  };

  const openPreview = async (p: AdminPaymentResponse) => {
    // Signed URLs expire after a few minutes; fetch a fresh one.
    try {
      setPreview(await adminPaymentsApi.get(p.id));
    } catch (err: any) {
      setError(err.message || 'Could not load screenshot');
    }
  };

  if (!allowed) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-950">
        <div className="w-6 h-6 border-2 border-neutral-700 border-t-amber-400 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 font-['Plus_Jakarta_Sans',sans-serif]">
      <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <Link href="/dashboard" className="inline-flex items-center gap-1 text-xs text-neutral-400 hover:text-white">
              <ArrowLeft className="w-3.5 h-3.5" />
              Dashboard
            </Link>
            <h1 className="text-2xl font-bold text-white font-['Syne',sans-serif] mt-1">UPI Payments</h1>
            <p className="text-xs text-neutral-400">
              Match each amount and UTR against your bank or UPI app before approving.
            </p>
          </div>
          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 text-neutral-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search UTR, user or amount"
              className="w-full pl-9 pr-3 py-2.5 rounded-xl bg-neutral-900 border border-neutral-800 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:border-amber-500/60"
            />
          </div>
        </div>

        <div className="flex gap-1 p-1 rounded-xl bg-neutral-900 border border-neutral-800 w-fit">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-colors ${
                tab === t.id ? 'bg-amber-500 text-neutral-950' : 'text-neutral-300 hover:text-white'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">{error}</div>
        )}

        {!loading && payments.length === 0 && (
          <p className="text-sm text-neutral-400 py-12 text-center">No payments here.</p>
        )}

        <ul className="space-y-3">
          {payments.map((p) => (
            <li key={p.id} className="p-4 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-3">
              <div className="flex flex-wrap items-start gap-4">
                {p.screenshot_url ? (
                  <button
                    onClick={() => openPreview(p)}
                    className="w-16 h-16 rounded-lg overflow-hidden border border-neutral-700 hover:border-amber-500/60 shrink-0"
                    title="View screenshot"
                  >
                    <img src={p.screenshot_url} alt="Payment screenshot" className="w-full h-full object-cover" />
                  </button>
                ) : (
                  <div className="w-16 h-16 rounded-lg bg-neutral-800 shrink-0" />
                )}

                <div className="flex-1 min-w-[12rem] space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-bold text-white">{p.user_name || p.user_email}</p>
                    <PaymentStatusBadge status={p.status} />
                  </div>
                  <p className="text-xs text-neutral-400">{p.user_email}</p>
                  <p className="text-[11px] text-neutral-500">Submitted {formatDateTime(p.created_at)}</p>
                  {p.rejection_reason && <p className="text-[11px] text-red-400">Reason: {p.rejection_reason}</p>}
                  {p.verified_at && (
                    <p className="text-[11px] text-neutral-500">Reviewed {formatDateTime(p.verified_at)}</p>
                  )}
                </div>

                <div className="space-y-1 text-right">
                  <p className="text-lg font-bold text-white">{formatAmount(p.amount, p.currency)}</p>
                  <p className="text-xs text-neutral-400">{p.plan_name}</p>
                  {p.utr_number && (
                    <button
                      onClick={() => navigator.clipboard.writeText(p.utr_number!)}
                      className="inline-flex items-center gap-1 text-xs font-mono text-amber-400 hover:text-amber-300"
                      title="Copy UTR"
                    >
                      {p.utr_number}
                      <Copy className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>

              {p.status === 'pending' && rejecting?.id !== p.id && (
                <div className="flex gap-2 justify-end">
                  <button
                    onClick={() => setRejecting({ id: p.id, reason: '' })}
                    disabled={busyId === p.id}
                    className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-red-500/20 text-red-300 font-bold text-xs transition-colors disabled:opacity-50 flex items-center gap-1"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    Reject
                  </button>
                  <button
                    onClick={() => approve(p)}
                    disabled={busyId === p.id}
                    className="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-neutral-950 font-bold text-xs transition-colors disabled:opacity-50 flex items-center gap-1"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Approve
                  </button>
                </div>
              )}

              {rejecting?.id === p.id && (
                <div className="p-3 rounded-xl bg-neutral-950 border border-red-500/30 space-y-2">
                  <div className="flex flex-wrap gap-1.5">
                    {REJECT_PRESETS.map((preset) => (
                      <button
                        key={preset}
                        onClick={() => setRejecting({ id: p.id, reason: preset })}
                        className="px-2.5 py-1 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-[11px] text-neutral-200"
                      >
                        {preset}
                      </button>
                    ))}
                  </div>
                  <textarea
                    value={rejecting.reason}
                    onChange={(e) => setRejecting({ id: p.id, reason: e.target.value })}
                    placeholder="Reason shown to the user (required)"
                    rows={2}
                    maxLength={500}
                    className="w-full px-3 py-2 rounded-lg bg-neutral-900 border border-neutral-800 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:border-red-500/60"
                  />
                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => setRejecting(null)}
                      className="px-3 py-1.5 rounded-lg text-xs text-neutral-300 hover:text-white"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => runAction(p.id, () => adminPaymentsApi.reject(p.id, rejecting.reason.trim()))}
                      disabled={busyId === p.id || rejecting.reason.trim().length < 3}
                      className="px-4 py-1.5 rounded-lg bg-red-500 hover:bg-red-400 text-white font-bold text-xs disabled:opacity-50"
                    >
                      Confirm Reject
                    </button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>

        {loading && (
          <div className="flex justify-center py-6">
            <div className="w-6 h-6 border-2 border-neutral-700 border-t-amber-400 rounded-full animate-spin" />
          </div>
        )}

        {hasMore && !loading && (
          <div className="flex justify-center">
            <button
              onClick={() => load(payments.length)}
              className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-xs font-bold text-white"
            >
              Load more
            </button>
          </div>
        )}
      </div>

      {preview?.screenshot_url && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-4"
          onClick={() => setPreview(null)}
        >
          <div className="max-w-3xl w-full space-y-2" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between text-xs text-neutral-300">
              <span>
                {preview.user_email} · {formatAmount(preview.amount, preview.currency)} · UTR{' '}
                <span className="font-mono">{preview.utr_number}</span>
              </span>
              <button onClick={() => setPreview(null)} className="px-2 py-1 rounded-lg bg-neutral-800 hover:bg-neutral-700">
                ✕
              </button>
            </div>
            <img
              src={preview.screenshot_url}
              alt="Payment screenshot, full size"
              className="max-h-[85vh] w-auto mx-auto rounded-xl border border-neutral-800"
            />
          </div>
        </div>
      )}
    </div>
  );
}
