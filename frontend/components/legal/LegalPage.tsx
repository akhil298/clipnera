import React from 'react';
import Link from 'next/link';

/** Set NEXT_PUBLIC_CONTACT_EMAIL before publishing the legal pages. */
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL || '';
export const LEGAL_UPDATED = '26 September 2026';

export function LegalPage({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-300 font-['Plus_Jakarta_Sans',sans-serif]">
      <article className="max-w-3xl mx-auto px-4 py-12 space-y-6 text-sm leading-relaxed [&_h2]:text-base [&_h2]:font-bold [&_h2]:text-white [&_h2]:pt-4 [&_a]:text-amber-300 [&_a:hover]:underline [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1">
        <Link href="/" className="text-xs text-neutral-400">
          ← Clipnera
        </Link>
        <h1 className="text-2xl font-bold text-white font-['Syne',sans-serif]">{title}</h1>
        <p className="text-xs text-neutral-500">Last updated {LEGAL_UPDATED}</p>
        {children}
      </article>
    </div>
  );
}

export function ContactLine() {
  return CONTACT_EMAIL ? (
    <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
  ) : (
    <span>the contact address shown in the app</span>
  );
}
