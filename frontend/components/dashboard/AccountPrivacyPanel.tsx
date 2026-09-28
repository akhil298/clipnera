'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Bell, Trash2 } from 'lucide-react';
import { userApi } from '@/lib/api';
import { clearAuth } from '@/lib/auth';
import type { UserProfile } from '@/lib/types';

interface AccountPrivacyPanelProps {
  user: UserProfile;
  onUpdateUser: (user: UserProfile) => void;
}

/** Account email opt-out and self-service account deletion (Settings → Profile). */
export function AccountPrivacyPanel({ user, onUpdateUser }: AccountPrivacyPanelProps) {
  const router = useRouter();
  const [savingEmails, setSavingEmails] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [confirmEmail, setConfirmEmail] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleEmails = async () => {
    setSavingEmails(true);
    setError(null);
    try {
      const profile = await userApi.setEmailPreferences({ email_notifications: !user.emailNotifications });
      onUpdateUser({ ...user, emailNotifications: profile.email_notifications });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save your email preference.');
    } finally {
      setSavingEmails(false);
    }
  };

  const deleteAccount = async () => {
    setDeleting(true);
    setError(null);
    try {
      await userApi.deleteAccount({ confirm_email: confirmEmail });
      clearAuth();
      router.replace('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete your account.');
      setDeleting(false);
    }
  };

  return (
    <div className="max-w-2xl p-6 rounded-2xl bg-neutral-900/90 border border-neutral-800 space-y-6 shadow-xl">
      <h3 className="text-sm font-bold text-white">Privacy &amp; data</h3>

      <div className="flex items-start justify-between gap-4">
        <div>
          <p id="email-notifications-label" className="text-xs font-bold text-white flex items-center gap-1.5">
            <Bell className="w-3.5 h-3.5 text-amber-400" aria-hidden="true" />
            Account emails
          </p>
          <p className="text-[11px] text-neutral-400 mt-1">
            Emails when a scheduled post fails or a connected account needs reconnecting. We never send marketing emails.
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={user.emailNotifications}
          aria-labelledby="email-notifications-label"
          onClick={toggleEmails}
          disabled={savingEmails}
          className={`relative shrink-0 w-10 h-6 rounded-full transition-colors disabled:opacity-50 ${
            user.emailNotifications ? 'bg-amber-500' : 'bg-neutral-700'
          }`}
        >
          <span
            className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform ${
              user.emailNotifications ? 'translate-x-4' : ''
            }`}
          />
        </button>
      </div>

      <div className="pt-5 border-t border-neutral-800 space-y-3">
        <p className="text-xs font-bold text-white flex items-center gap-1.5">
          <Trash2 className="w-3.5 h-3.5 text-rose-400" aria-hidden="true" />
          Delete account
        </p>
        <p className="text-[11px] text-neutral-400">
          Permanently deletes your account, videos, clips, reels, brand kits, payment records and connected social
          accounts. Unused credits and any paid time left are lost. This cannot be undone. See the{' '}
          <a href="/privacy" className="text-amber-300 underline underline-offset-2">privacy policy</a>.
        </p>

        {confirming ? (
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              void deleteAccount();
            }}
          >
            <label className="block text-[11px] text-neutral-300">
              Type <b className="text-white">{user.email}</b> to confirm:
              <input
                type="email"
                value={confirmEmail}
                onChange={(e) => setConfirmEmail(e.target.value)}
                autoComplete="off"
                autoFocus
                className="mt-1.5 w-full p-2.5 rounded-xl bg-neutral-950 border border-neutral-700 text-xs text-white focus:outline-none focus:border-rose-400"
              />
            </label>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={deleting || confirmEmail.trim().toLowerCase() !== user.email.toLowerCase()}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deleting ? 'Deleting…' : 'Permanently delete my account'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirming(false);
                  setConfirmEmail('');
                }}
                className="px-4 py-2 rounded-xl bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-xs font-bold"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            className="px-4 py-2 rounded-xl border border-rose-500/40 text-rose-300 hover:bg-rose-500/10 text-xs font-bold"
          >
            Delete account…
          </button>
        )}
      </div>

      {error && (
        <p role="alert" className="text-xs text-rose-300">
          {error}
        </p>
      )}
    </div>
  );
}
