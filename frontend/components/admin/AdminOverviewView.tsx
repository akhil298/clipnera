'use client';

import React, { useEffect, useState } from 'react';
import { adminUsersApi, AdminDailyGrowth, AdminGrowthResponse, AdminOverviewResponse } from '@/lib/api';
import { formatDay } from '@/lib/utils/dates';
import { formatAmount } from '@/lib/utils/payments';
import { AdminLayout } from './AdminLayout';
import { AdminError, AdminSpinner, AdminTable, RangeTabs, StatTile, usd } from './AdminUi';
import { DailyBarChart } from './DailyBarChart';

const count = (value: number) => Math.round(value).toLocaleString();

/** The per-day measures charted, in reading order. */
const GROWTH_CHARTS: { key: keyof Omit<AdminDailyGrowth, 'day'>; title: string; money?: 'inr' | 'usd' }[] = [
  { key: 'signups', title: 'Sign-ups' },
  { key: 'active_users', title: 'Active users' },
  { key: 'logins', title: 'Logins' },
  { key: 'projects', title: 'Projects created' },
  { key: 'clips', title: 'Clips generated' },
  { key: 'revenue', title: 'Revenue (approved payments)', money: 'inr' },
  { key: 'ai_cost_usd', title: 'AI cost', money: 'usd' },
];

function GrowthSection({ growth }: { growth: AdminGrowthResponse }) {
  const [showTable, setShowTable] = useState(false);
  const inr = (value: number) => formatAmount(value, growth.currency);
  const formatFor = (money?: 'inr' | 'usd') => (money === 'inr' ? inr : money === 'usd' ? usd : count);
  const period = `last ${growth.days} days`;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile label="Total users" value={count(growth.total_users)} hint={`${count(growth.new_users)} new in the ${period}`} href="/admin/users" />
        <StatTile label="Active today" value={count(growth.active_today)} hint="Used the app today (UTC)" />
        <StatTile label="Active, last 7 days" value={count(growth.active_7d)} />
        <StatTile label="Active, last 30 days" value={count(growth.active_30d)} />
        <StatTile label={`Projects, ${period}`} value={count(growth.projects)} />
        <StatTile label={`Clips, ${period}`} value={count(growth.clips)} />
        <StatTile label={`Revenue, ${period}`} value={inr(growth.revenue)} />
        <StatTile label={`AI cost, ${period}`} value={usd(growth.ai_cost_usd)} href="/admin/usage" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {GROWTH_CHARTS.map(({ key, title, money }) => {
          const format = formatFor(money);
          // Daily actives do not add up across days: the range total is distinct users.
          const total = key === 'active_users' ? count(growth.active_in_window) : format(growth.daily.reduce((sum, d) => sum + d[key], 0));
          return (
            <DailyBarChart
              key={key}
              title={title}
              total={total}
              points={growth.daily.map((d) => ({ day: d.day, value: d[key] }))}
              format={format}
              wholeNumbers={!money}
            />
          );
        })}
      </div>

      <div className="space-y-2">
        <button
          type="button"
          onClick={() => setShowTable((shown) => !shown)}
          className="text-xs font-bold text-amber-300 hover:text-amber-200"
        >
          {showTable ? 'Hide day-by-day table' : 'Show day-by-day table'}
        </button>
        {showTable && (
          <AdminTable
            head={['Day', ...GROWTH_CHARTS.map((c) => c.title)]}
            rows={[...growth.daily].reverse().map((d) => [
              formatDay(d.day),
              ...GROWTH_CHARTS.map(({ key, money }) => formatFor(money)(d[key])),
            ])}
            empty="No days in this range."
          />
        )}
      </div>
    </div>
  );
}

export function AdminOverviewView() {
  const [overview, setOverview] = useState<AdminOverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [growth, setGrowth] = useState<AdminGrowthResponse | null>(null);
  const [growthError, setGrowthError] = useState<string | null>(null);

  useEffect(() => {
    adminUsersApi
      .getOverview()
      .then(setOverview)
      .catch((err: Error) => setError(err.message || 'Could not load overview'));
  }, []);

  useEffect(() => {
    setGrowth(null);
    setGrowthError(null);
    adminUsersApi
      .getGrowth(days)
      .then(setGrowth)
      .catch((err: Error) => setGrowthError(err.message || 'Could not load growth'));
  }, [days]);

  return (
    <AdminLayout title="Overview" subtitle="Plans and revenue at a glance. Revenue counts payments approved this calendar month (UTC).">
      {error && <AdminError message={error} />}
      {!overview && !error && <AdminSpinner />}
      {overview && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatTile label="Free users" value={overview.free_users.toLocaleString()} href="/admin/users" />
          <StatTile label="Active Pro users" value={overview.pro_users.toLocaleString()} href="/admin/users" />
          <StatTile label="Revenue this month" value={formatAmount(overview.revenue_this_month, overview.currency)} />
          <StatTile label="Pending payments" value={overview.pending_payments.toLocaleString()} href="/admin/payments" />
        </div>
      )}

      <section className="space-y-3 pt-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-white">Growth</h2>
            <p className="text-[11px] text-neutral-400">
              Per UTC day. Active users and logins are counted from the day tracking went live; everything else covers all history.
            </p>
          </div>
          <RangeTabs value={days} onChange={setDays} />
        </div>
        {growthError && <AdminError message={growthError} />}
        {!growth && !growthError && <AdminSpinner />}
        {growth && <GrowthSection growth={growth} />}
      </section>
    </AdminLayout>
  );
}
