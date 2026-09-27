import React from 'react';
import Link from 'next/link';

/**
 * Who runs Clipnera, shown on the legal pages and in the footer. Set these
 * NEXT_PUBLIC_* variables before publishing; a field left empty is not shown.
 */
export const BUSINESS = {
  legalName: process.env.NEXT_PUBLIC_LEGAL_NAME || '',
  address: process.env.NEXT_PUBLIC_BUSINESS_ADDRESS || '',
  gstin: process.env.NEXT_PUBLIC_GSTIN || '',
  contactEmail: process.env.NEXT_PUBLIC_CONTACT_EMAIL || '',
  // Grievance Officer required by India's IT Rules 2021 and DPDP Act 2023.
  grievanceOfficer: process.env.NEXT_PUBLIC_GRIEVANCE_OFFICER || '',
  grievanceEmail: process.env.NEXT_PUBLIC_GRIEVANCE_EMAIL || process.env.NEXT_PUBLIC_CONTACT_EMAIL || '',
};

export const LEGAL_UPDATED = '27 September 2026';

/** Local storage flag set when the cookie notice is closed; listed in the cookie policy. */
export const COOKIE_NOTICE_KEY = 'cookie_notice_dismissed';

export const LEGAL_LINKS = [
  { href: '/terms', label: 'Terms of Service' },
  { href: '/privacy', label: 'Privacy Policy' },
  { href: '/refunds', label: 'Refund Policy' },
  { href: '/cookies', label: 'Cookie Policy' },
  { href: '/data-deletion', label: 'Delete your data' },
] as const;

export function LegalPage({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-300 font-['Plus_Jakarta_Sans',sans-serif]">
      <main className="max-w-3xl mx-auto px-4 py-12 space-y-6 text-sm leading-relaxed [&_h2]:text-base [&_h2]:font-bold [&_h2]:text-white [&_h2]:pt-4 [&_a]:text-amber-300 [&_a]:underline [&_a]:underline-offset-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-1">
        <Link href="/" className="text-xs text-neutral-400">
          ← Clipnera
        </Link>
        <h1 className="text-2xl font-bold text-white font-['Syne',sans-serif]">{title}</h1>
        <p className="text-xs text-neutral-400">Last updated {LEGAL_UPDATED}</p>
        {children}
        <nav aria-label="Legal" className="pt-8 border-t border-neutral-800 flex flex-wrap gap-x-5 gap-y-2 text-xs">
          {LEGAL_LINKS.map((link) => (
            <Link key={link.href} href={link.href}>
              {link.label}
            </Link>
          ))}
        </nav>
      </main>
    </div>
  );
}

export function ContactLine() {
  return BUSINESS.contactEmail ? (
    <a href={`mailto:${BUSINESS.contactEmail}`}>{BUSINESS.contactEmail}</a>
  ) : (
    <span>the contact address shown in the app</span>
  );
}

/** The operator's identity and how to reach them, for the Contact section of each policy. */
export function BusinessDetails() {
  return (
    <ul>
      {BUSINESS.legalName && <li>Operated by {BUSINESS.legalName}</li>}
      {BUSINESS.address && <li>Address: {BUSINESS.address}</li>}
      {BUSINESS.gstin && <li>GSTIN: {BUSINESS.gstin}</li>}
      <li>
        Email: <ContactLine />
      </li>
      {BUSINESS.grievanceOfficer && (
        <li>
          Grievance Officer: {BUSINESS.grievanceOfficer}
          {BUSINESS.grievanceEmail && (
            <>
              {' '}
              (<a href={`mailto:${BUSINESS.grievanceEmail}`}>{BUSINESS.grievanceEmail}</a>)
            </>
          )}
        </li>
      )}
    </ul>
  );
}
