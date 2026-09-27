'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, Crown } from 'lucide-react';
import { adminUsersApi, AdminUserDetailResponse } from '@/lib/api';
import { isPaidPlanSlug, planLabel } from '@/hooks/useEntitlements';
import { formatDate, formatDay, parseApiDate } from '@/lib/utils/dates';
import { BILLING_PERIOD_LABELS, formatAmount, formatDateTime } from '@/lib/utils/payments';
import { AdminLayout } from './AdminLayout';
import { AdminError, AdminSpinner, AdminTable, StatTile, usd } from './AdminUi';

const TIMELINE_PREVIEW = 30;
const METHOD_LABELS: Record<string, string> = { password: 'Email & password', google: 'Google', microsoft: 'Microsoft' };

/** Browser and OS from a user-agent string, e.g. "Chrome on Windows". */
function deviceLabel(userAgent: string | null): string {
  if (!userAgent) return '—';
  const browser = /Edg\//.test(userAgent)
    ? 'Edge'
    : /Chrome\//.test(userAgent)
      ? 'Chrome'
      : /Firefox\//.test(userAgent)
        ? 'Firefox'
        : /Safari\//.test(userAgent)
          ? 'Safari'
          : 'Browser';
  const os = /Android/.test(userAgent)
    ? 'Android'
    : /iPhone|iPad/.test(userAgent)
      ? 'iOS'
      : /Windows/.test(userAgent)
        ? 'Windows'
        : /Mac OS X/.test(userAgent)
          ? 'macOS'
          : /Linux/.test(userAgent)
            ? 'Linux'
            : 'unknown OS';
  return `${browser} on ${os}`;
}

/** Only web links become clickable; the URL is user-supplied. */
function SourceLink({ url }: { url: string | null }) {
  if (!url) return <span className="text-neutral-500">Upload</span>;
  if (!/^https?:\/\//i.test(url)) return <span className="break-all">{url}</span>;
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="text-amber-300 hover:text-amber-200 break-all">
      {url}
    </a>
  );
}

interface TimelineEvent {
  at: string;
  label: string;
  detail?: React.ReactNode;
}

function buildTimeline(detail: AdminUserDetailResponse): TimelineEvent[] {
  const events: TimelineEvent[] = [
    { at: detail.user.created_at, label: 'Signed up' },
    ...detail.logins.map((login) => ({
      at: login.created_at,
      label: `Logged in with ${METHOD_LABELS[login.method] ?? login.method}`,
      detail: [login.ip, deviceLabel(login.user_agent)].filter(Boolean).join(' · '),
    })),
    ...detail.projects.map((project) => ({
      at: project.created_at,
      label: `Created project "${project.title}"`,
      detail: <SourceLink url={project.source_url} />,
    })),
    ...detail.payments.map((payment) => ({
      at: payment.created_at,
      label: `Submitted a ${formatAmount(payment.amount, payment.currency)} payment`,
      detail: `Now ${payment.status}`,
    })),
  ];
  return events.sort((a, b) => parseApiDate(b.at).getTime() - parseApiDate(a.at).getTime());
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-bold text-white">{title}</h2>
      {children}
    </section>
  );
}

export function AdminUserDetailView() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<AdminUserDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showFullTimeline, setShowFullTimeline] = useState(false);

  useEffect(() => {
    adminUsersApi
      .getDetail(id)
      .then(setDetail)
      .catch((err: Error) => setError(err.message || 'Could not load this user'));
  }, [id]);

  const timeline = useMemo(() => (detail ? buildTimeline(detail) : []), [detail]);
  const user = detail?.user;
  const isPro = user ? isPaidPlanSlug(user.plan) : false;

  return (
    <AdminLayout
      title={user ? user.name || user.email : 'User'}
      subtitle={user ? `${user.email} · joined ${formatDate(user.created_at)}` : 'Everything this user has done.'}
      actions={
        <Link href="/admin/users" className="inline-flex items-center gap-1 text-xs text-neutral-400 hover:text-white">
          <ArrowLeft className="w-3.5 h-3.5" /> All users
        </Link>
      }
    >
      {error && <AdminError message={error} />}
      {!detail && !error && <AdminSpinner />}
      {detail && user && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatTile
              label="Plan"
              value={planLabel(user.plan)}
              hint={isPro && user.plan_expires_at ? `Until ${formatDate(user.plan_expires_at)}` : undefined}
            />
            <StatTile
              label="Credits left"
              value={`${user.credits_left} / ${detail.credits_total}`}
              hint={detail.next_credit_reset_at ? `Resets ${formatDate(detail.next_credit_reset_at)}` : undefined}
            />
            <StatTile label="Projects" value={user.projects.toLocaleString()} hint={`${user.clips.toLocaleString()} clips generated`} />
            <StatTile label="Total paid" value={formatAmount(user.total_paid, 'INR')} />
            <StatTile label="AI cost" value={usd(user.ai_cost_usd)} />
            <StatTile label="Days active" value={detail.active_days.toLocaleString()} hint="Since tracking went live" />
            <StatTile label="Last active" value={user.last_active_on ? formatDay(user.last_active_on) : '—'} />
            <StatTile label="Last login" value={user.last_login_at ? formatDate(user.last_login_at) : '—'} />
          </div>

          <Section title="Timeline">
            {timeline.length === 0 ? (
              <p className="text-xs text-neutral-500">Nothing yet.</p>
            ) : (
              <ol className="rounded-2xl border border-neutral-800 bg-neutral-900/90 divide-y divide-neutral-800/60">
                {(showFullTimeline ? timeline : timeline.slice(0, TIMELINE_PREVIEW)).map((event, i) => (
                  <li key={i} className="px-4 py-2.5 flex flex-wrap items-baseline gap-x-4 gap-y-1">
                    <span className="text-[11px] font-mono text-neutral-500 w-40 shrink-0">{formatDateTime(event.at)}</span>
                    <span className="text-sm text-neutral-200">{event.label}</span>
                    {event.detail && <span className="text-xs text-neutral-400 min-w-0">{event.detail}</span>}
                  </li>
                ))}
              </ol>
            )}
            {timeline.length > TIMELINE_PREVIEW && (
              <button
                type="button"
                onClick={() => setShowFullTimeline((shown) => !shown)}
                className="text-xs font-bold text-amber-300 hover:text-amber-200"
              >
                {showFullTimeline ? 'Show less' : `Show all ${timeline.length} events`}
              </button>
            )}
          </Section>

          <Section title="Projects">
            <AdminTable
              head={['Project', 'Status', 'Length', 'Clips', 'Credits', 'AI cost', 'Created']}
              rows={detail.projects.map((project) => [
                <div key="p" className="space-y-0.5 min-w-[16rem]">
                  <p className="font-bold text-white">{project.title}</p>
                  <p className="text-xs">
                    <SourceLink url={project.source_url} />
                  </p>
                </div>,
                project.status,
                project.duration_seconds ? `${Math.round(project.duration_seconds / 60)} min` : '—',
                project.clips.toLocaleString(),
                project.credits_charged.toLocaleString(),
                usd(project.ai_cost_usd),
                formatDateTime(project.created_at),
              ])}
              empty="No projects yet."
            />
          </Section>

          <Section title="Logins">
            <AdminTable
              head={['When', 'Method', 'IP address', 'Device']}
              rows={detail.logins.map((login) => [
                formatDateTime(login.created_at),
                METHOD_LABELS[login.method] ?? login.method,
                login.ip ?? '—',
                <span key="d" title={login.user_agent ?? undefined}>{deviceLabel(login.user_agent)}</span>,
              ])}
              empty="No logins recorded yet. Logins are tracked from the day tracking went live."
            />
          </Section>

          <Section title="Payments">
            <AdminTable
              head={['Submitted', 'Amount', 'Bought', 'Status', 'Approved']}
              rows={detail.payments.map((payment) => [
                formatDateTime(payment.created_at),
                formatAmount(payment.amount, payment.currency),
                payment.plan_type
                  ? `Pro, ${BILLING_PERIOD_LABELS[payment.plan_type as keyof typeof BILLING_PERIOD_LABELS] ?? payment.plan_type}`
                  : `${payment.credits ?? 0} credits pack`,
                payment.status,
                payment.verified_at ? formatDateTime(payment.verified_at) : '—',
              ])}
              empty="No payments."
            />
          </Section>

          <Section title="Credit history">
            <AdminTable
              head={['When', 'Change', 'Balance', 'Reason']}
              rows={detail.credit_history.map((entry) => [
                formatDateTime(entry.created_at),
                <span key="c" className={entry.amount < 0 ? 'text-red-300' : 'text-emerald-300'}>
                  {entry.amount > 0 ? `+${entry.amount}` : entry.amount}
                </span>,
                entry.balance_after.toLocaleString(),
                <span key="r" className="font-sans text-neutral-300">{entry.reason}</span>,
              ])}
              empty="No credit activity."
            />
          </Section>
        </div>
      )}
    </AdminLayout>
  );
}
