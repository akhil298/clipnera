import Link from 'next/link';

import { BUSINESS, LEGAL_LINKS } from '@/components/legal/LegalPage';
import { Wordmark } from '@/components/ui';
import { cx, focusRing } from '@/lib/design/styles';

const LINK = cx('rounded-cn-xs text-cn-fg-secondary hover:text-cn-fg', focusRing);

/** Wordmark, tagline, legal links and the operator's details (shown only when configured). */
export function SiteFooter() {
  const details = [BUSINESS.address, BUSINESS.gstin && `GSTIN ${BUSINESS.gstin}`].filter(Boolean).join(' · ');
  return (
    <footer className="border-t border-cn-border bg-cn-bg">
      <div className="mx-auto flex max-w-screen-xl flex-col gap-6 px-4 py-10 sm:px-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Link href="/" aria-label="Clipnera home" className={cx('rounded-cn-sm', focusRing)}>
            <Wordmark size="sm" />
          </Link>
          <p className="text-cn-label text-cn-fg-muted">Long video in. Shorts out.</p>
        </div>
        <nav aria-label="Legal">
          <ul className="flex flex-wrap gap-x-5 gap-y-2 text-cn-label">
            {LEGAL_LINKS.map((link) => (
              <li key={link.href}>
                <Link href={link.href} className={LINK}>
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex flex-col gap-1 text-cn-caption text-cn-fg-muted">
          <p>
            © {new Date().getFullYear()} {BUSINESS.legalName || 'Clipnera AI'}. All rights reserved.
          </p>
          {(details || BUSINESS.contactEmail) && (
            <p>
              {details}
              {details && BUSINESS.contactEmail && ' · '}
              {BUSINESS.contactEmail && (
                <a href={`mailto:${BUSINESS.contactEmail}`} className={cx(LINK, 'underline underline-offset-2')}>
                  {BUSINESS.contactEmail}
                </a>
              )}
            </p>
          )}
        </div>
      </div>
    </footer>
  );
}
