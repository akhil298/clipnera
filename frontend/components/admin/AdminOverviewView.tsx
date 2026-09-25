'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { adminUsersApi, AdminOverviewResponse } from '@/lib/api';
import { formatAmount } from '@/lib/utils/payments';
import { AdminLayout } from './AdminLayout';

function StatTile({ label, value, href }: { label: string; value: string; href?: string }) {
  const body = (
    <div className="p-4 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-1 h-full">
      <p className="text-[11px] font-bold text-neutral-400">{label}</p>
      <p className="text-2xl font-bold text-white font-mono">{value}</p>
    </div>
  );
  return href ? (
    <Link href={href} className="block hover:opacity-90">
      {body}
    </Link>
  ) : (
    body
  );
}

export function AdminOverviewView() {
  const [overview, setOverview] = useState<AdminOverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminUsersApi
      .getOverview()
      .then(setOverview)
      .catch((err: Error) => setError(err.message || 'Could not load overview'));
  }, []);

  return (
    <AdminLayout title="Overview" subtitle="Plans and revenue at a glance. Revenue counts payments approved this calendar month (UTC).">
      {error && <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">{error}</div>}
      {!overview && !error && (
        <div className="flex justify-center py-12">
          <div className="w-6 h-6 border-2 border-neutral-700 border-t-amber-400 rounded-full animate-spin" />
        </div>
      )}
      {overview && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatTile label="Free users" value={overview.free_users.toLocaleString()} href="/admin/users" />
          <StatTile label="Active Pro users" value={overview.pro_users.toLocaleString()} href="/admin/users" />
          <StatTile label="Revenue this month" value={formatAmount(overview.revenue_this_month, overview.currency)} />
          <StatTile label="Pending payments" value={overview.pending_payments.toLocaleString()} href="/admin/payments" />
        </div>
      )}
    </AdminLayout>
  );
}
