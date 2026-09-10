'use client';

import React, { useState } from 'react';
import { CreditCard, CheckCircle2, XCircle, Copy, ExternalLink } from 'lucide-react';
import { subscriptionApi, PaymentTransactionResponse } from '@/lib/api';

interface PaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  plan: {
    id: string;
    name: string;
    slug: string;
    credit_minutes: number;
    price_monthly: number;
    currency: string;
  } | null;
  onPaymentComplete: () => void;
}

export function PaymentModal({ isOpen, onClose, plan, onPaymentComplete }: PaymentModalProps) {
  const [step, setStep] = useState<'confirm' | 'pending' | 'success' | 'failed'>('confirm');
  const [transaction, setTransaction] = useState<PaymentTransactionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handlePay = async () => {
    if (!plan) return;
    setLoading(true);
    setError(null);
    try {
      const tx = await subscriptionApi.initiatePayment(plan.slug, 'manual', 'Manual payment initiated from UI');
      setTransaction(tx);
      setStep('pending');
    } catch (err: any) {
      setError(err.message || 'Failed to initiate payment');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (status: 'success' | 'failed') => {
    if (!transaction) return;
    setLoading(true);
    setError(null);
    try {
      const updated = await subscriptionApi.verifyPayment(transaction.payment_uuid, status, `Admin verified: ${status}`);
      setTransaction(updated);
      setStep(status === 'success' ? 'success' : 'failed');
      if (status === 'success') {
        onPaymentComplete();
      }
    } catch (err: any) {
      setError(err.message || 'Failed to verify payment');
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  if (!isOpen || !plan) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl shadow-2xl max-w-md w-full">
        <div className="p-6 lg:p-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-white font-['Syne',sans-serif]">
              {step === 'confirm' && 'Complete Payment'}
              {step === 'pending' && 'Payment Pending'}
              {step === 'success' && 'Payment Successful'}
              {step === 'failed' && 'Payment Failed'}
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
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-neutral-300">Plan</span>
                  <span className="text-sm font-bold text-white">{plan.name}</span>
                </div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-neutral-300">Credits</span>
                  <span className="text-sm font-bold text-amber-400">{plan.credit_minutes} min</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-neutral-300">Amount</span>
                  <span className="text-sm font-bold text-white">
                    {plan.price_monthly === 0 ? 'Free' : `${plan.currency} ${plan.price_monthly}`}
                  </span>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
                <p className="text-xs text-amber-300 leading-relaxed">
                  You will be redirected to complete your payment. After successful payment, your credits will be added to your account automatically.
                </p>
              </div>

              <button
                onClick={handlePay}
                disabled={loading}
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

          {step === 'pending' && transaction && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-neutral-300">Payment UUID</span>
                  <button
                    onClick={() => copyToClipboard(transaction.payment_uuid)}
                    className="flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300"
                  >
                    <Copy className="w-3 h-3" />
                    Copy
                  </button>
                </div>
                <p className="text-xs font-mono text-neutral-400 break-all">{transaction.payment_uuid}</p>
              </div>

              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
                <p className="text-xs text-amber-300 leading-relaxed">
                  Your payment is pending verification. Use the UUID above to verify your payment. Once verified, your credits will be added automatically.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-neutral-950 border border-neutral-800">
                <p className="text-xs text-neutral-400 mb-2">Admin Actions</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleVerify('success')}
                    disabled={loading}
                    className="flex-1 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-neutral-950 font-bold text-xs active:scale-95 transition-all disabled:opacity-50 flex items-center justify-center gap-1"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Verify Success
                  </button>
                  <button
                    onClick={() => handleVerify('failed')}
                    disabled={loading}
                    className="flex-1 py-2 rounded-xl bg-red-500 hover:bg-red-400 text-white font-bold text-xs active:scale-95 transition-all disabled:opacity-50 flex items-center justify-center gap-1"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    Mark Failed
                  </button>
                </div>
              </div>
            </div>
          )}

          {step === 'success' && (
            <div className="space-y-4 text-center py-4">
              <div className="w-16 h-16 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-8 h-8 text-emerald-400" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Payment Verified!</h3>
                <p className="text-sm text-neutral-400 mt-1">Your {plan.credit_minutes} credits have been added to your account.</p>
              </div>
              <button
                onClick={onClose}
                className="px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-neutral-950 font-bold text-sm shadow-md shadow-amber-500/15 active:scale-95 transition-all"
              >
                Done
              </button>
            </div>
          )}

          {step === 'failed' && (
            <div className="space-y-4 text-center py-4">
              <div className="w-16 h-16 rounded-full bg-red-500/20 border border-red-500/40 flex items-center justify-center mx-auto">
                <XCircle className="w-8 h-8 text-red-400" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Payment Failed</h3>
                <p className="text-sm text-neutral-400 mt-1">The payment could not be verified. Please try again.</p>
              </div>
              <button
                onClick={onClose}
                className="px-6 py-2.5 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-white font-bold text-sm active:scale-95 transition-all"
              >
                Close
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
