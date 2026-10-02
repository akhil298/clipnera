'use client';

import { useEffect } from 'react';
import { X } from 'lucide-react';
import { GoogleSignIn } from '@/components/auth/GoogleSignIn';

/** The Google sign-in dialog the public pages open from "Sign in" and "Start free". */
export function SignInModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Sign in to Clipnera"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md"
    >
      <div className="relative w-full max-w-md rounded-2xl bg-neutral-900/90 border border-neutral-800 p-6 shadow-xl">
        <button
          onClick={onClose}
          aria-label="Close"
          autoFocus
          className="absolute top-5 right-5 p-1.5 rounded-full text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
        >
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
        <GoogleSignIn />
      </div>
    </div>
  );
}
