'use client';

import React, { useEffect, useState } from 'react';
import { CreditCard, CheckCircle2, Copy, Check, ImageUp, Smartphone } from 'lucide-react';
import { paymentsApi, type CreditPackResponse, type UpiCheckoutResponse } from '@/lib/api';
import type { SelectedPlan } from './PlanSelectionModal';
import {
  BILLING_PERIOD_LABELS,
  formatAmount,
  normalizeUtr,
  MAX_SCREENSHOT_BYTES,
  SCREENSHOT_TYPES,
  UTR_PATTERN,
} from '@/lib/utils/payments';

interface PaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  plan: SelectedPlan | null;
  /** A credit pack to buy instead of a plan. */
  creditPack?: CreditPackResponse | null;
  onPaymentComplete: () => void;
}

type Step = 'confirm' | 'pay' | 'submitted';

function screenshotError(file: File): string | null {
  if (!SCREENSHOT_TYPES.includes(file.type)) return 'Screenshot must be a JPG, PNG or WebP image.';
  if (file.size > MAX_SCREENSHOT_BYTES) return 'Screenshot must be 5 MB or smaller.';
  return null;
}

export function PaymentModal({ isOpen, onClose, plan, creditPack = null, onPaymentComplete }: PaymentModalProps) {
  const [step, setStep] = useState<Step>('confirm');
  const [checkout, setCheckout] = useState<UpiCheckoutResponse | null>(null);
  const [screenshot, setScreenshot] = useState<File | null>(null);
  const [utr, setUtr] = useState('');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const planSlug = plan?.slug;
  const planType = plan?.planType;
  const packSlug = creditPack?.slug;

  // Each time the modal opens for a purchase, start over and load its UPI
  // price. The amount always comes from the server; the user cannot change it.
  useEffect(() => {
    if (!isOpen || !(packSlug || (planSlug && planType))) return;
    let cancelled = false;
    setStep('confirm');
    setCheckout(null);
    setScreenshot(null);
    setUtr('');
    setError(null);
    setLoading(true);
    (packSlug ? paymentsApi.getCreditPackCheckout(packSlug) : paymentsApi.getCheckout(planSlug!, planType!))
      .then((data) => {
        if (!cancelled) setCheckout(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message || 'Could not load payment details');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, planSlug, planType, packSlug]);

  const utrValid = UTR_PATTERN.test(normalizeUtr(utr));
  const canSubmit = Boolean(checkout && screenshot && utrValid && !loading);

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    const problem = screenshotError(file);
    setError(problem);
    setScreenshot(problem ? null : file);
  };

  const handleSubmit = async () => {
    if (!checkout || !screenshot || !utrValid) return;
    setLoading(true);
    setError(null);
    try {
      const utrNumber = normalizeUtr(utr);
      if (creditPack) {
        await paymentsApi.submitCreditPack({ credit_pack: creditPack.slug, utr_number: utrNumber, screenshot });
      } else if (plan) {
        await paymentsApi.submit({ plan_slug: plan.slug, plan_type: plan.planType, utr_number: utrNumber, screenshot });
      }
      setStep('submitted');
    } catch (err: any) {
      setError(err.message || 'Failed to submit payment');
    } finally {
      setLoading(false);
    }
  };

  const copyUpiId = async () => {
    if (!checkout) return;
    await navigator.clipboard.writeText(checkout.upi_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  if (!isOpen || (!plan && !creditPack)) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl shadow-2xl max-w-md w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6 lg:p-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-white font-['Syne',sans-serif]">
              {step === 'confirm' && 'Complete Payment'}
              {step === 'pay' && 'Pay with UPI'}
              {step === 'submitted' && 'Payment Submitted'}
            </h2>
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-neutral-800 border border-neutral-700 text-neutral-300 hover:text-white hover:border-neutral-600 transition-colors"
            >
              ✕
            </button>
          </div>

          {error && (
            <div className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
              {error}
            </div>
          )}

          {step === 'confirm' && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800">
                {creditPack ? (
                  <>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-neutral-300">Credit pack</span>
                      <span className="text-sm font-bold text-white">{creditPack.name}</span>
                    </div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-neutral-300">Credits</span>
                      <span className="text-sm font-bold text-amber-400">{creditPack.credits} · never expire</span>
                    </div>
                  </>
                ) : plan && (
                  <>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-neutral-300">Plan</span>
                      <span className="text-sm font-bold text-white">{plan.name}</span>
                    </div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-neutral-300">Billing</span>
                      <span className="text-sm font-bold text-white">{BILLING_PERIOD_LABELS[plan.planType]}</span>
                    </div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-neutral-300">Credits</span>
                      <span className="text-sm font-bold text-amber-400">{plan.creditMinutes} every 30 days</span>
                    </div>
                  </>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-sm text-neutral-300">Amount</span>
                  <span className="text-sm font-bold text-white">
                    {checkout ? formatAmount(checkout.amount, checkout.currency) : '—'}
                  </span>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
                <p className="text-xs text-amber-300 leading-relaxed">
                  Pay by scanning our UPI QR code with any UPI app, then upload the payment screenshot and UTR.{' '}
                  {creditPack
                    ? 'Your credits are added as soon as we verify the payment.'
                    : 'Your plan is activated as soon as we verify the payment.'}
                </p>
              </div>

              <button
                onClick={() => setStep('pay')}
                disabled={loading || !checkout}
                className="w-full py-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-sm shadow-md shadow-amber-500/15 active:scale-95 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <div className="w-5 h-5 border-2 border-neutral-900/30 border-t-neutral-900 rounded-full animate-spin" />
                ) : (
                  <>
                    <CreditCard className="w-4 h-4" />
                    <span>Pay Now</span>
                  </>
                )}
              </button>
            </div>
          )}

          {step === 'pay' && checkout && (
            <div className="space-y-5">
              <div className="flex flex-col items-center gap-3">
                {/* QR codes need a light background to scan reliably. */}
                <div className="p-3 rounded-xl bg-white">
                  <img src={checkout.qr_image} alt={`UPI QR code to pay ${checkout.payee_name}`} className="w-52 h-52" />
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-white">{formatAmount(checkout.amount, checkout.currency)}</p>
                  <p className="text-xs text-neutral-400">to {checkout.payee_name}</p>
                </div>
                <a
                  href={checkout.upi_uri}
                  className="md:hidden flex items-center gap-1.5 text-xs font-bold text-amber-400 hover:text-amber-300"
                >
                  <Smartphone className="w-3.5 h-3.5" />
                  Open UPI app
                </a>
              </div>

              <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-neutral-400">UPI ID</span>
                  <button
                    onClick={copyUpiId}
                    className="flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300"
                  >
                    {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <p className="text-sm font-mono text-white break-all">{checkout.upi_id}</p>
              </div>

              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
                <p className="text-xs text-amber-300 leading-relaxed">
                  After paying, upload the screenshot and enter the UTR / transaction ID.
                </p>
              </div>

              <div className="space-y-3">
                <label className="block">
                  <span className="text-xs font-bold text-neutral-300">Payment screenshot</span>
                  <div className="mt-1.5 flex items-center gap-3 p-3 rounded-xl bg-neutral-950 border border-dashed border-neutral-700 hover:border-amber-500/50 cursor-pointer transition-colors">
                    <ImageUp className="w-5 h-5 text-neutral-400 shrink-0" />
                    <span className="text-xs text-neutral-300 truncate">
                      {screenshot ? screenshot.name : 'JPG, PNG or WebP, up to 5 MB'}
                    </span>
                  </div>
                  <input
                    type="file"
                    accept={SCREENSHOT_TYPES.join(',')}
                    className="sr-only"
                    onChange={(e) => {
                      handleFile(e.target.files?.[0]);
                      e.target.value = '';
                    }}
                  />
                </label>

                <label className="block">
                  <span className="text-xs font-bold text-neutral-300">UTR / transaction ID</span>
                  <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    placeholder="12-digit UTR number"
                    value={utr}
                    onChange={(e) => setUtr(e.target.value)}
                    maxLength={16}
                    className="mt-1.5 w-full px-3 py-2.5 rounded-xl bg-neutral-950 border border-neutral-800 text-sm font-mono text-white placeholder:text-neutral-600 focus:outline-none focus:border-amber-500/60"
                  />
                  {utr && !utrValid && (
                    <span className="mt-1 block text-[11px] text-red-400">UTR must be exactly 12 digits.</span>
                  )}
                </label>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => setStep('confirm')}
                  disabled={loading}
                  className="px-4 py-3 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-white font-bold text-sm active:scale-95 transition-all disabled:opacity-50"
                >
                  Back
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={!canSubmit}
                  className="flex-1 py-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-sm shadow-md shadow-amber-500/15 active:scale-95 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <div className="w-5 h-5 border-2 border-neutral-900/30 border-t-neutral-900 rounded-full animate-spin" />
                  ) : (
                    'Submit Payment'
                  )}
                </button>
              </div>
            </div>
          )}

          {step === 'submitted' && (
            <div className="space-y-4 text-center py-4">
              <div className="w-16 h-16 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-8 h-8 text-emerald-400" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Payment submitted</h3>
                <p className="text-sm text-neutral-400 mt-1">
                  {creditPack ? 'Your credits will be added once we verify the payment' : 'Pro activation is pending verification'}, which usually takes a few minutes. Track it under Settings → Plan &amp; Billing → My Payments.
                </p>
              </div>
              <button
                onClick={onPaymentComplete}
                className="px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-sm shadow-md shadow-amber-500/15 active:scale-95 transition-all"
              >
                Done
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
