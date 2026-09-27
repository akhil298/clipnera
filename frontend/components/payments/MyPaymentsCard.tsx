'use client';

import React, { useEffect, useState } from 'react';
import { Receipt } from 'lucide-react';
import { paymentsApi, PaymentResponse } from '@/lib/api';
import { formatAmount, formatDateTime, paymentLabel } from '@/lib/utils/payments';
import { PaymentStatusBadge } from './PaymentStatusBadge';

/** The signed-in user's UPI payments and where each one stands. */
export function MyPaymentsCard({ refreshKey = 0 }: { refreshKey?: number }) {
  const [payments, setPayments] = useState<PaymentResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    paymentsApi
      .getMine()
      .then((data) => {
        if (!cancelled) setPayments(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || 'Could not load payments');
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return (
    <div className="p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-4 shadow-xl">
      <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
        <Receipt className="w-4 h-4 text-amber-400" />
        <span>My Payments</span>
      </h3>

      {error && <p className="text-xs text-red-400">{error}</p>}

      {!error && payments === null && (
        <div className="animate-pulse space-y-2">
          <div className="h-12 bg-neutral-800 rounded-xl" />
          <div className="h-12 bg-neutral-800 rounded-xl" />
        </div>
      )}

      {payments?.length === 0 && <p className="text-xs text-neutral-400">No payments yet.</p>}

      {payments && payments.length > 0 && (
        <ul className="space-y-2">
          {payments.map((p) => (
            <li
              key={p.id}
              className="p-3 rounded-xl bg-neutral-950 border border-neutral-800 flex flex-wrap items-center justify-between gap-2"
            >
              <div className="min-w-0">
                <p className="text-xs font-bold text-white">
                  {paymentLabel(p)} · {formatAmount(p.amount, p.currency)}
                </p>
                <p className="text-[11px] text-neutral-400">
                  {formatDateTime(p.created_at)}
                  {p.utr_number && <span className="font-mono"> · UTR {p.utr_number}</span>}
                </p>
                {p.status === 'rejected' && p.rejection_reason && (
                  <p className="text-[11px] text-red-400 mt-0.5">Reason: {p.rejection_reason}</p>
                )}
              </div>
              <PaymentStatusBadge status={p.status} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
