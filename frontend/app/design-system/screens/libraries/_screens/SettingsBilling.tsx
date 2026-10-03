'use client';

import { Check, CircleCheck, Copy, Crown, Lock, Minus, RotateCcw, Smartphone } from 'lucide-react';
import { useState } from 'react';

import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { ProgressSteps } from '@/components/ui/ProgressSteps';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Skeleton, SkeletonGroup } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';
import { cx } from '@/lib/design/styles';

import { Callout, DataTable, Dropzone, KeyValues, RadioGroup, StorageMeter, UsageMeter } from '../_components/Additions';
import { MockFrame } from '../_components/MockFrame';
import { SettingsCard, SettingsFrame } from '../_components/SettingsFrame';

const STATES = [
  { id: 'pro', label: 'Pro, active' },
  { id: 'free', label: 'Free' },
  { id: 'pending', label: 'Payment pending' },
  { id: 'rejected', label: 'Payment rejected' },
  { id: 'expiring', label: 'Pro ends in 3 days' },
  { id: 'loading', label: 'Loading' },
  { id: 'error', label: 'Plan failed to load' },
  { id: 'plans', label: 'Plans dialog' },
  { id: 'pay-confirm', label: 'Pay: confirm' },
  { id: 'pay-upi', label: 'Pay: UPI' },
  { id: 'pay-invalid', label: 'Pay: UTR invalid' },
  { id: 'pay-submitted', label: 'Pay: submitted' },
  { id: 'pay-error', label: 'Pay: price failed to load' },
  { id: 'pay-unavailable', label: 'Pay: UPI unavailable' },
] as const;

export function SettingsBilling() {
  return (
    <MockFrame title="Settings · Plan and billing" url="/dashboard/settings/billing (+ @modal plans, payment)" flag="new_ui_settings" states={STATES}>
      {(state, setState) => <Body state={state} setState={setState} />}
    </MockFrame>
  );
}

const PAYMENTS = [
  { id: 'p1', what: 'Pro Monthly', amount: '₹699', when: '3 Oct 2026, 11:20 am', utr: '412398765012', status: 'pending' as const },
  { id: 'p2', what: '200 credits', amount: '₹299', when: '12 Sep 2026, 9:05 pm', utr: '409911223344', status: 'rejected' as const, reason: 'Amount mismatch: we received ₹29.' },
  { id: 'p3', what: 'Pro Monthly', amount: '₹699', when: '3 Sep 2026, 10:41 am', utr: '408877665544', status: 'success' as const },
];

const PAY_STATUS = { pending: <StatusBadge status="processing">Checking</StatusBadge>, success: <StatusBadge status="ready">Approved</StatusBadge>, rejected: <StatusBadge status="failed">Rejected</StatusBadge> };

function Body({ state, setState }: { state: string; setState: (s: string) => void }) {
  const free = state === 'free';
  const pending = state === 'pending';
  if (state === 'loading') {
    return (
      <SettingsFrame section="billing">
        <SkeletonGroup label="Loading your plan" className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-40 rounded-cn-lg" />
          <Skeleton className="h-40 rounded-cn-lg" />
          <Skeleton className="h-32 rounded-cn-lg md:col-span-2" />
        </SkeletonGroup>
      </SettingsFrame>
    );
  }
  return (
    <SettingsFrame section="billing">
      {state === 'error' && (
        <Callout tone="danger" live="alert" title="Your plan didn't load." action={<Button size="sm" variant="secondary">Try again</Button>}>
          Your plan and credits haven't changed. We don't show numbers we can't confirm.
        </Callout>
      )}
      {pending && (
        <Callout tone="info" title="We're checking your payment of ₹699." action={<Button size="sm" variant="ghost">View payment</Button>}>
          Usually within a few hours. Pro switches on by itself and you'll get a notification. You can keep using Clipnera meanwhile.
        </Callout>
      )}
      {state === 'rejected' && (
        <Callout tone="danger" title="Your payment for 200 credits wasn't approved." action={<Button size="sm" variant="secondary" leadingIcon={<RotateCcw />} onClick={() => setState('pay-upi')}>Pay again</Button>}>
          Reason: Amount mismatch: we received ₹29. If you paid the full amount, reply to the notification email with your bank statement.
        </Callout>
      )}
      {state === 'expiring' && (
        <Callout tone="warning" title="Pro ends on 6 Oct." action={<Button size="sm" onClick={() => setState('plans')}>Renew Pro</Button>}>
          Pro doesn't renew by itself. Renewing adds the new period on top of your current end date.
        </Callout>
      )}

      {state !== 'error' && (
        <div className="grid gap-4 md:grid-cols-2">
          <SettingsCard id="plan-card" title={free ? 'Free plan' : 'Pro'} description={free ? 'Free forever. Upgrade any time.' : 'Paid until 3 Nov 2026'} actions={free ? <Badge>Free</Badge> : pending ? <StatusBadge status="processing">Pending verification</StatusBadge> : <Badge tone="success" icon={<Crown />}>Active</Badge>}>
            <Button
              variant={free || state === 'expiring' ? 'primary' : 'secondary'}
              disabled={pending}
              onClick={() => setState('plans')}
            >
              {free ? 'Upgrade to Pro' : 'Renew Pro'}
            </Button>
            {pending && <p className="mt-2 text-cn-label text-cn-fg-muted">You can renew once this payment is checked.</p>}
          </SettingsCard>

          <SettingsCard id="credits-card" title="Credits" description={free ? '≈ 7 min of video at 2 credits a minute.' : '≈ 270 min of video at 2 credits a minute.'}>
            <p className="font-cn-mono text-cn-title-lg font-semibold tabular-nums text-cn-fg">
              {free ? '14' : '540'} <span className="text-cn-body text-cn-fg-muted">/ {free ? '20' : '740'}</span>
            </p>
            <div role="img" aria-label={free ? '14 plan credits left' : '400 plan credits and 140 pack credits left'} className="mt-2 flex h-2 overflow-hidden rounded-cn-full bg-cn-surface-active">
              <span className="h-full bg-cn-accent" style={{ width: free ? '70%' : '54%' }} />
              {!free && <span className="h-full bg-cn-accent/40" style={{ width: '19%' }} />}
            </div>
            <ul className="mt-2 space-y-0.5 text-cn-label text-cn-fg-secondary">
              <li className="flex items-center gap-2"><span aria-hidden className="size-2 rounded-cn-full bg-cn-accent" /> <span className="font-cn-mono">{free ? 14 : 400}</span> plan credits · reset to {free ? 20 : 600} on 3 Nov; unused ones don't roll over</li>
              {!free && <li className="flex items-center gap-2"><span aria-hidden className="size-2 rounded-cn-full bg-cn-accent/40" /> <span className="font-cn-mono">140</span> pack credits · never expire, used after plan credits</li>}
            </ul>
          </SettingsCard>
        </div>
      )}

      {state !== 'error' && (
        <SettingsCard title="Used today" description="Resets at 5:30 am IST (midnight UTC).">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <UsageMeter label="Exports" used={free ? 10 : 7} limit={free ? 10 : null} />
            <UsageMeter label="Audio clean-ups" used={1} limit={free ? 3 : null} />
            <UsageMeter label="Reel renders" used={2} limit={free ? 2 : 20} />
            <UsageMeter label="AI shots" used={free ? 0 : 1} limit={free ? 0 : 10} />
            <UsageMeter label="Footage edits" used={0} limit={free ? 1 : 15} />
            <UsageMeter label="Channel intro renders" used={0} limit={free ? 0 : 5} />
          </div>
          <div className="mt-5 border-t border-cn-border pt-4">
            <StorageMeter used={free ? 0.3 : 3.2} total={free ? 1 : 25} items={free ? 5 : 48} breakdown={free ? undefined : [{ label: 'Uploads', value: 2.6 }, { label: 'AI shots', value: 0.2 }, { label: 'Recently deleted', value: 0.4 }]} />
          </div>
        </SettingsCard>
      )}

      <SettingsCard title="Buy credits" description="One-off top-ups on any plan. Bought credits never expire and are used after your plan's monthly credits.">
        <ul className="grid gap-3 sm:grid-cols-3">
          {[
            { name: 'Starter', credits: 60, price: 99 },
            { name: 'Creator', credits: 200, price: 299 },
            { name: 'Studio', credits: 500, price: 649 },
          ].map((p) => (
            <li key={p.name} className="flex flex-col gap-2 rounded-cn-lg border border-cn-border p-4">
              <p className="text-cn-label text-cn-fg-secondary">{p.name}</p>
              <p className="font-cn-mono text-cn-title font-semibold tabular-nums text-cn-fg">{p.credits} <span className="text-cn-label font-normal text-cn-fg-muted">credits</span></p>
              <p className="text-cn-caption text-cn-fg-muted">≈ {p.credits / 2} min of video · ₹{(p.price / p.credits).toFixed(2)} a credit</p>
              <Button variant="secondary" className="mt-auto" onClick={() => setState('pay-confirm')}>Buy for ₹{p.price}</Button>
            </li>
          ))}
        </ul>
      </SettingsCard>

      <SettingsCard title="Payments" description="Each payment is checked by hand against our UPI account, usually within a few hours.">
        <DataTable
          caption="Your payments"
          rows={PAYMENTS}
          columns={[
            { key: 'what', header: 'For', primary: true, render: (p) => p.what },
            { key: 'amount', header: 'Amount', numeric: true, render: (p) => p.amount },
            { key: 'when', header: 'Submitted', render: (p) => <span className="text-cn-fg-secondary">{p.when}</span> },
            { key: 'utr', header: 'UTR', render: (p) => <span className="font-cn-mono text-cn-label">{p.utr}</span> },
            { key: 'status', header: 'Status', render: (p) => <span className="space-y-1">{PAY_STATUS[p.status]}{p.reason && <span className="block text-cn-caption text-cn-danger-text">{p.reason}</span>}</span> },
            { key: 'act', header: 'Actions', hideHeader: true, render: (p) => (p.status === 'rejected' ? <Button size="sm" variant="ghost" onClick={() => setState('pay-upi')}>Pay again</Button> : null) },
          ]}
        />
      </SettingsCard>

      <PlansDialog open={state === 'plans'} onClose={() => setState(free ? 'free' : 'pro')} onChoose={() => setState('pay-confirm')} free={free} />
      <PaymentDialog state={state} setState={setState} />
    </SettingsFrame>
  );
}

const ROWS: ReadonlyArray<{ label: string; free: string | boolean; pro: string | boolean }> = [
  { label: 'Credits every 30 days', free: '20', pro: '600' },
  { label: 'Videos up to', free: '30 min', pro: '120 min' },
  { label: 'Clips per video', free: '5', pro: '20' },
  { label: 'Formats', free: '9:16', pro: '9:16, 1:1, 4:5, 16:9' },
  { label: 'Choose output formats per video', free: false, pro: true },
  { label: 'Caption styles', free: '6', pro: 'Every style' },
  { label: 'Exports a day', free: '10', pro: 'Unlimited' },
  { label: 'Audio enhancements a day', free: '3', pro: 'Unlimited' },
  { label: 'Library storage', free: '1 GB', pro: '25 GB' },
  { label: 'No watermark', free: false, pro: true },
  { label: 'Pro AI models', free: false, pro: true },
  { label: 'All hook transitions', free: false, pro: true },
  { label: 'Create and edit brand kits', free: false, pro: true },
  { label: 'Add team members', free: false, pro: true },
  { label: 'Depth captions', free: false, pro: true },
  { label: 'Batch processing', free: false, pro: true },
  { label: 'Connected social accounts', free: '1', pro: '4' },
  { label: 'Social posts a day', free: '3', pro: '25' },
  { label: 'Schedule social posts', free: false, pro: true },
];

function Cell({ value }: { value: string | boolean }) {
  if (value === true) return <span className="inline-flex items-center gap-1 text-cn-success-text"><Check aria-hidden className="size-4" /><span className="sr-only">Included</span></span>;
  if (value === false) return <span className="inline-flex items-center gap-1 text-cn-fg-muted"><Minus aria-hidden className="size-4" /><span className="sr-only">Not included</span></span>;
  return <span className="font-cn-mono text-cn-label tabular-nums text-cn-fg">{value}</span>;
}

/** Plan comparison. Rows come from the server's plan rules (comparisonRows), never hard-coded in production. */
function PlansDialog({ open, onClose, onChoose, free }: { open: boolean; onClose: () => void; onChoose: () => void; free: boolean }) {
  const [period, setPeriod] = useState<'monthly' | 'yearly'>('monthly');
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      size="lg"
      title="Choose your plan"
      description="Start free. Upgrade when you need more."
      footer={
        <>
          <p className="mr-auto hidden text-cn-caption text-cn-fg-muted sm:block">Pro doesn't renew by itself. Renewing adds time on top of your current end date.</p>
          <Button variant="ghost" onClick={onClose}>Not now</Button>
          <Button onClick={onChoose}>{free ? 'Upgrade to Pro' : 'Renew Pro'} · {period === 'monthly' ? '₹699' : '₹6,990'}</Button>
        </>
      }
    >
      <div className="space-y-4">
        <Badge tone="accent" icon={<Lock />}>Depth captions — available on Pro</Badge>
        <SegmentedControl label="Billing period" options={[{ value: 'monthly', label: 'Monthly' }, { value: 'yearly', label: 'Yearly · 2 months free' }]} value={period} onValueChange={setPeriod} />
        <table className="w-full border-collapse text-left">
          <caption className="sr-only">Free and Pro compared</caption>
          <thead>
            <tr className="border-b border-cn-border align-bottom">
              <th scope="col" className="py-2 text-cn-caption font-medium text-cn-fg-muted"><span className="sr-only">Feature</span></th>
              <th scope="col" className="w-1/4 py-2">
                <span className="block text-cn-body font-semibold text-cn-fg">Free</span>
                <span className="font-cn-mono text-cn-title font-semibold">₹0</span>
                {free && <Badge className="ml-2">Current</Badge>}
              </th>
              <th scope="col" className="w-1/4 rounded-t-cn-md bg-cn-accent-subtle px-2 py-2">
                <span className="flex items-center gap-1 text-cn-body font-semibold text-cn-accent-text"><Crown aria-hidden className="size-4" /> Pro</span>
                <span className="font-cn-mono text-cn-title font-semibold">{period === 'monthly' ? '₹699' : '₹6,990'}</span>
                <span className="text-cn-caption text-cn-fg-muted"> /{period === 'monthly' ? 'month' : 'year'}</span>
                {!free && <Badge className="ml-2">Current</Badge>}
              </th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((r) => (
              <tr key={r.label} className="border-b border-cn-border">
                <th scope="row" className="py-2 pr-2 text-cn-label font-normal text-cn-fg-secondary">{r.label}</th>
                <td className="py-2"><Cell value={r.free} /></td>
                <td className="bg-cn-accent-subtle px-2 py-2"><Cell value={r.pro} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Dialog>
  );
}

/**
 * Checkout. Step 2 is a payment-method slot: today the only method is manual
 * UPI (QR + proof). A gateway (UPI collect / cards) slots in as a second
 * RadioGroup option whose step 2 is the provider's own flow, and whose
 * "submitted" step skips "checking by hand".
 */
function PaymentDialog({ state, setState }: { state: string; setState: (s: string) => void }) {
  const { show } = useToast();
  const [method, setMethod] = useState<'upi_manual' | 'gateway'>('upi_manual');
  const open = state.startsWith('pay-');
  const step = state === 'pay-submitted' ? 2 : state === 'pay-upi' || state === 'pay-invalid' ? 1 : 0;
  const close = () => {
    setState(state === 'pay-submitted' ? 'pending' : 'pro');
    if (state === 'pay-submitted') show({ title: 'Payment submitted', description: "We'll notify you once it's checked.", tone: 'success' });
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => !o && close()}
      title={['Confirm your purchase', 'Pay with UPI', 'Payment submitted'][step]}
      footer={
        step === 0 ? (
          <>
            <Button variant="ghost" onClick={close}>Cancel</Button>
            <Button disabled={state === 'pay-error' || state === 'pay-unavailable'} onClick={() => setState('pay-upi')}>Continue to pay ₹699</Button>
          </>
        ) : step === 1 ? (
          <>
            <Button variant="ghost" onClick={() => setState('pay-confirm')}>Back</Button>
            <Button onClick={() => setState(state === 'pay-upi' ? 'pay-invalid' : 'pay-submitted')}>Submit payment</Button>
          </>
        ) : (
          <Button onClick={close}>Done</Button>
        )
      }
    >
      <div className="space-y-5">
        <ProgressSteps
          label="Checkout"
          steps={['Confirm', 'Pay', 'Submitted'].map((label, i) => ({ id: label, label, status: i < step || step === 2 ? 'done' : i === step ? 'active' : 'upcoming' }))}
        />
        {step === 0 && (
          <>
            {state === 'pay-error' && (
              <Callout tone="danger" live="alert" title="The price didn't load." action={<Button size="sm" variant="secondary">Try again</Button>}>Nothing was charged.</Callout>
            )}
            {state === 'pay-unavailable' && (
              <Callout tone="warning" live="alert" title="UPI payments aren't available right now.">Nothing was charged. Try again in a little while, or write to us and we'll help.</Callout>
            )}
            <KeyValues items={[{ label: 'Plan', value: 'Pro · Monthly' }, { label: 'Credits', value: '600 every 30 days' }, { label: 'Amount', value: <span className="font-cn-mono text-cn-title-sm font-semibold">₹699</span> }]} />
            <RadioGroup
              legend="Pay with"
              layout="cards"
              options={[
                { value: 'upi_manual', label: 'Any UPI app', description: 'Scan a QR, then upload the screenshot and UTR. Checked by hand.' },
                { value: 'gateway', label: 'Card or UPI autopay', description: 'Coming later', disabled: true },
              ]}
              value={method}
              onValueChange={setMethod}
            />
            <p className="text-cn-caption text-cn-fg-muted">
              One-time payment; Pro does not renew automatically. Payments are non-refundable except as described in our <a href="/refunds" className="text-cn-accent-text underline underline-offset-2">Refund Policy</a>. Credits used by processing that fails are always returned.
            </p>
          </>
        )}
        {step === 1 && (
          <>
            <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-start">
              <div aria-label="UPI QR code for ₹699 to Clipnera" role="img" className="grid size-44 shrink-0 grid-cols-8 gap-0.5 rounded-cn-md bg-white p-3">
                {Array.from({ length: 64 }, (_, i) => <span key={i} className={cx('rounded-cn-xs', (i * 7 + (i >> 3)) % 3 === 0 ? 'bg-black' : 'bg-transparent')} />)}
              </div>
              <div className="min-w-0 space-y-2 text-center sm:text-left">
                <p className="font-cn-mono text-cn-display-sm font-bold tabular-nums">₹699</p>
                <p className="text-cn-label text-cn-fg-secondary">to Clipnera</p>
                <div className="flex items-center gap-2 rounded-cn-md bg-cn-surface-hover px-3 py-1.5">
                  <span className="font-cn-mono text-cn-label">clipnera@okaxis</span>
                  <Button size="sm" variant="ghost" leadingIcon={<Copy />} onClick={() => show({ title: 'UPI ID copied' })}>Copy</Button>
                </div>
                <Button size="sm" variant="secondary" leadingIcon={<Smartphone />} className="sm:hidden">Open UPI app</Button>
              </div>
            </div>
            <Callout tone="neutral">After paying, upload the screenshot and type the 12-digit UTR (transaction ID) from your UPI app.</Callout>
            <Dropzone compact title="Add payment screenshot" hint="JPG, PNG or WebP, up to 5 MB." accept="image/jpeg,image/png,image/webp" />
            <Input
              label="UTR number"
              inputMode="numeric"
              autoComplete="off"
              defaultValue={state === 'pay-invalid' ? '41239876501' : ''}
              placeholder="12 digits"
              hint="Spaces are fine; we remove them."
              error={state === 'pay-invalid' ? 'UTR must be exactly 12 digits. This one has 11.' : undefined}
            />
          </>
        )}
        {step === 2 && (
          <div className="space-y-3 text-center">
            <CircleCheck aria-hidden className="mx-auto size-10 text-cn-success-text" />
            <p className="text-cn-body text-cn-fg">Pro activation is pending verification, which usually takes a few minutes. Track it under Settings → Plan and billing → Payments.</p>
          </div>
        )}
      </div>
    </Dialog>
  );
}
