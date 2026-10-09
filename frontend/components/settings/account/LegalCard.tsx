import { ChevronRight } from 'lucide-react';
import Link from 'next/link';

import { BUSINESS } from '@/components/legal/LegalPage';
import { cx, focusRing } from '@/lib/design/styles';

import { sectionById, SettingsCard, SettingsRow } from '../frame';

/** The public compliance pages (legacy routes, never rewritten), one click from Settings → Account. */
const LEGAL_PAGES = [
  { href: '/terms', label: 'Terms of service', description: 'The agreement for using Clipnera' },
  { href: '/privacy', label: 'Privacy policy', description: 'What we collect, why, and your rights' },
  { href: '/refunds', label: 'Refund policy', description: 'When a payment can be refunded' },
  { href: '/cookies', label: 'Cookie policy', description: 'What this site stores in your browser' },
  { href: '/data-deletion', label: 'How to delete your data', description: 'Also works if you can no longer sign in' },
] as const;

const linkClass = cx('rounded-cn-xs text-cn-accent-text underline underline-offset-2', focusRing);

export function LegalCard() {
  const grievance = BUSINESS.grievanceOfficer || BUSINESS.grievanceEmail;
  return (
    <SettingsCard id="legal" title="Legal and your data" description="The policies that apply to your account, and how to have your data removed.">
      <ul className="-my-1 divide-y divide-cn-border">
        {LEGAL_PAGES.map((page) => (
          <li key={page.href}>
            <Link
              href={page.href}
              className={cx('-mx-2 flex min-h-14 items-center gap-3 rounded-cn-md px-2 py-2 hover:bg-cn-surface-hover active:bg-cn-surface-active', focusRing)}
            >
              <span className="min-w-0 flex-1">
                <span className="block text-cn-label font-semibold text-cn-fg">{page.label}</span>
                <span className="block text-cn-caption text-cn-fg-secondary">{page.description}</span>
              </span>
              <ChevronRight aria-hidden className="size-4 shrink-0 text-cn-fg-muted" />
            </Link>
          </li>
        ))}
        {grievance && (
          <li>
            <SettingsRow
              label="Grievance officer"
              description={
                <>
                  {BUSINESS.grievanceOfficer}
                  {BUSINESS.grievanceOfficer && BUSINESS.grievanceEmail && ' · '}
                  {BUSINESS.grievanceEmail && (
                    <a href={`mailto:${BUSINESS.grievanceEmail}`} className={cx(linkClass, 'break-all')}>
                      {BUSINESS.grievanceEmail}
                    </a>
                  )}
                </>
              }
            />
          </li>
        )}
      </ul>
      <p className="mt-3 text-cn-caption text-cn-fg-secondary">
        Account emails can also be turned off from any email’s unsubscribe link, or in{' '}
        <Link href={sectionById('notifications').href} className={linkClass}>
          Notifications
        </Link>
        .
      </p>
    </SettingsCard>
  );
}
