'use client';

import { useState } from 'react';
import { Check, Minus } from 'lucide-react';
import { formatAmount } from '@/lib/utils/payments';
import { SectionIntro } from './SectionIntro';

interface PricingSectionProps {
  onLaunchStudio: () => void;
}

type Period = 'monthly' | 'yearly';

// Static copy of the server's plan rules (backend/subscription/entitlements.py:
// PLAN_PRICES, CREDIT_PACKS, ENTITLEMENTS). Change both together; the server's amounts are what get charged.
const PRO_PRICE: Record<Period, { amount: number; suffix: string }> = {
  monthly: { amount: 699, suffix: '/month' },
  yearly: { amount: 6990, suffix: '/year' },
};
const YEARLY_SAVING = Math.round((1 - PRO_PRICE.yearly.amount / (PRO_PRICE.monthly.amount * 12)) * 100);
const CREDITS_PER_MINUTE = 2;
const FREE_CREDITS = 20;
const PRO_CREDITS = 600;

const CREDIT_PACKS = [
  { name: 'Starter', credits: 60, amount: 99 },
  { name: 'Creator', credits: 200, amount: 299 },
  { name: 'Studio', credits: 500, amount: 649 },
];

const minutesOf = (credits: number) => credits / CREDITS_PER_MINUTE;

const PLANS = [
  {
    name: 'Free',
    pitch: 'Try it on your own videos.',
    credits: FREE_CREDITS,
    cta: 'Start free',
    features: ['Up to 5 clips per video', 'Videos up to 30 minutes', '9:16 vertical clips', 'Captions, speaker framing and noise reduction', 'Post to 1 channel: YouTube, TikTok or Instagram'],
  },
  {
    name: 'Pro',
    pitch: 'For creators who post every week.',
    credits: PRO_CREDITS,
    cta: 'Get Pro',
    features: ['Up to 20 clips per video', 'Videos up to 2 hours', 'No watermark', 'Every caption style, brand kit and channel intro', 'Full reel editing with motion graphics', '4 channels including X, with scheduling up to 30 days'],
  },
];

const COMPARISON: Array<[string, string | boolean, string | boolean]> = [
  ['Credits every 30 days', `${FREE_CREDITS}`, `${PRO_CREDITS}`],
  ['Video you can process', `About ${minutesOf(FREE_CREDITS)} min`, `About ${minutesOf(PRO_CREDITS) / 60} hours`],
  ['Longest upload', '30 min', '2 hours'],
  ['Clips per video', '5', '20'],
  ['Formats', '9:16', '9:16, 1:1, 4:5, 16:9'],
  ['Watermark', 'Yes', 'No'],
  ['Caption styles', 'Starter set', 'All'],
  ['Pro AI models', false, true],
  ['Brand kits', false, true],
  ['Channel intro', false, true],
  ['Batch processing', false, true],
  ['Team members', false, true],
  ['Connected channels', '1', '4, including X'],
  ['Social posts a day', '3', '25'],
  ['Schedule posts', false, 'Up to 30 days ahead'],
  ['Exports a day', '10', 'Unlimited'],
];

function Cell({ value }: { value: string | boolean }) {
  if (value === true) return <Check className="mx-auto h-4 w-4 text-emerald-400" aria-label="Included" />;
  if (value === false) return <Minus className="mx-auto h-4 w-4 text-neutral-600" aria-label="Not included" />;
  return <>{value}</>;
}

/** Plans, credit packs and a side-by-side comparison, in rupees. */
export function PricingSection({ onLaunchStudio }: PricingSectionProps) {
  const [period, setPeriod] = useState<Period>('monthly');
  const pro = PRO_PRICE[period];

  return (
    <section id="pricing" className="scroll-mt-20 border-t border-neutral-900 py-20 lg:py-28">
      <div className="mx-auto max-w-[1240px] px-4 sm:px-8">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <SectionIntro eyebrow="01:02 · Pricing" title={<>Start free.<br />Upgrade when it&apos;s working.</>} />
          <div role="group" aria-label="Billing period" className="inline-flex self-start rounded-xl border border-neutral-800 bg-neutral-900 p-1 lg:self-auto">
            {(['monthly', 'yearly'] as const).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPeriod(p)}
                aria-pressed={period === p}
                className={`h-11 rounded-lg px-5 text-sm font-bold transition-colors ${period === p ? 'bg-white text-neutral-950' : 'text-neutral-300 hover:text-white'}`}
              >
                {p === 'monthly' ? 'Monthly' : `Yearly · save ${YEARLY_SAVING}%`}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-12 grid gap-6 md:grid-cols-2">
          {PLANS.map((plan) => {
            const paid = plan.name === 'Pro';
            return (
              <article
                key={plan.name}
                className={`flex flex-col gap-6 rounded-3xl p-7 sm:p-9 ${paid ? 'border-2 border-amber-500 bg-[#141008]' : 'border border-neutral-800 bg-[#121212]'}`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="font-syne text-2xl font-bold text-white">{plan.name}</h3>
                    <p className="mt-1 text-[15px] text-neutral-400">{plan.pitch}</p>
                  </div>
                  {paid && (
                    <span className="rounded-full bg-amber-500 px-3 py-1 font-jetbrains text-[11px] font-bold tracking-[0.06em] text-neutral-950">MOST POPULAR</span>
                  )}
                </div>
                <div>
                  <p className="flex items-baseline gap-1.5">
                    <span className="font-syne text-5xl font-extrabold tracking-[-0.03em] text-white">
                      {formatAmount(paid ? pro.amount : 0, 'INR')}
                    </span>
                    <span className="text-base font-semibold text-neutral-400">{paid ? pro.suffix : 'forever'}</span>
                  </p>
                  <p className="mt-2 text-[15px] text-neutral-300">
                    <span className="font-bold text-amber-400">{plan.credits} credits</span> every 30 days, about{' '}
                    {minutesOf(plan.credits) >= 60 ? `${minutesOf(plan.credits) / 60} hours` : `${minutesOf(plan.credits)} minutes`} of video
                    {paid && period === 'yearly' && <span className="text-neutral-400"> · {formatAmount(Math.round(pro.amount / 12), 'INR')} a month, billed yearly</span>}
                  </p>
                </div>
                <ul className="space-y-3 text-[15px] text-neutral-200">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2.5">
                      <Check className="mt-1 h-4 w-4 flex-shrink-0 text-emerald-400" aria-hidden="true" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  onClick={onLaunchStudio}
                  className={`mt-auto h-12 rounded-xl text-base font-extrabold transition-colors active:scale-[0.98] ${
                    paid ? 'bg-amber-500 text-neutral-950 hover:bg-amber-400' : 'border border-neutral-700 text-white hover:border-white'
                  }`}
                >
                  {plan.cta}
                </button>
              </article>
            );
          })}
        </div>

        <div className="mt-6 rounded-3xl border border-neutral-800 bg-[#121212] p-7 sm:p-9">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h3 className="font-syne text-xl font-bold text-white">Need more? Credit packs</h3>
              <p className="mt-1 text-[15px] text-neutral-400">One-time, on any plan. Bought credits never expire and are used after your plan&apos;s credits.</p>
            </div>
          </div>
          <ul className="mt-6 grid gap-4 sm:grid-cols-3">
            {CREDIT_PACKS.map((pack) => (
              <li key={pack.name} className="flex items-center justify-between rounded-2xl border border-neutral-800 bg-neutral-950 px-5 py-4">
                <div>
                  <p className="font-bold text-white">{pack.name}</p>
                  <p className="text-sm text-neutral-400">
                    {pack.credits} credits · about {minutesOf(pack.credits)} min
                  </p>
                </div>
                <p className="font-syne text-2xl font-extrabold text-white">{formatAmount(pack.amount, 'INR')}</p>
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-12 overflow-x-auto rounded-3xl border border-neutral-800">
          <table className="w-full min-w-[560px] border-collapse text-left text-[15px]">
            <caption className="sr-only">Free and Pro compared</caption>
            <thead>
              <tr className="bg-neutral-900 font-jetbrains text-xs tracking-[0.1em] text-neutral-400">
                <th scope="col" className="px-6 py-4 font-medium">COMPARE</th>
                <th scope="col" className="w-[26%] px-6 py-4 text-center font-medium">FREE</th>
                <th scope="col" className="w-[26%] px-6 py-4 text-center font-medium text-amber-400">PRO</th>
              </tr>
            </thead>
            <tbody>
              {COMPARISON.map(([label, free, proValue]) => (
                <tr key={label} className="border-t border-neutral-800">
                  <th scope="row" className="px-6 py-3.5 font-semibold text-neutral-200">{label}</th>
                  <td className="px-6 py-3.5 text-center text-neutral-400"><Cell value={free} /></td>
                  <td className="px-6 py-3.5 text-center text-white"><Cell value={proValue} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="mt-6 max-w-[80ch] text-sm text-neutral-400">
          Prices in Indian rupees; the amount shown is the amount you pay. Video uses {CREDITS_PER_MINUTE} credits a minute. Pro
          doesn&apos;t renew automatically. See our{' '}
          <a href="/refunds" className="text-amber-400 underline underline-offset-2">Refund Policy</a>.
        </p>
      </div>
    </section>
  );
}
