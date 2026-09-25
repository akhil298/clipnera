import React from 'react';
import type { PaymentStatus } from '@/lib/api';

const STYLES: Record<PaymentStatus, { label: string; className: string }> = {
  pending: { label: 'Pending', className: 'bg-amber-500/10 text-amber-300 border-amber-500/30' },
  success: { label: 'Success', className: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30' },
  rejected: { label: 'Rejected', className: 'bg-red-500/10 text-red-300 border-red-500/30' },
  failed: { label: 'Failed', className: 'bg-red-500/10 text-red-300 border-red-500/30' },
};

export function PaymentStatusBadge({ status }: { status: PaymentStatus }) {
  const { label, className } = STYLES[status];
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase border ${className}`}>{label}</span>
  );
}
