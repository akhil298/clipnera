'use client';

import Link from 'next/link';
import { BUSINESS, LEGAL_LINKS } from '@/components/legal/LegalPage';

interface FooterProps {
  onLaunchApp: () => void;
  onOpenAuthModal: () => void;
}

export function Footer({ onLaunchApp, onOpenAuthModal }: FooterProps) {
  return (
    <footer className="border-t border-neutral-800 bg-neutral-950 py-10 text-xs text-neutral-400">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div aria-hidden="true" className="w-6 h-6 rounded-lg bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-xs">
              C
            </div>
            <span className="font-bold text-white font-['Syne',sans-serif]">
              Clipnera AI Studio
            </span>
            <span>• Next-Gen Shorts Repurposing</span>
          </div>

          <nav aria-label="App" className="flex flex-wrap items-center justify-center gap-6 text-neutral-300">
            <button onClick={onLaunchApp} className="hover:text-white transition-colors">
              App Dashboard
            </button>
            <button onClick={onLaunchApp} className="hover:text-white transition-colors">
              Project Folders
            </button>
            <button onClick={onLaunchApp} className="hover:text-white transition-colors">
              Settings & Billing
            </button>
            <button onClick={onOpenAuthModal} className="hover:text-white transition-colors">
              Sign In
            </button>
          </nav>
        </div>

        <div className="pt-6 border-t border-neutral-800/80 flex flex-col md:flex-row items-center justify-between gap-4">
          <nav aria-label="Legal" className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-neutral-300">
            {LEGAL_LINKS.map((link) => (
              <Link key={link.href} href={link.href} className="hover:text-white transition-colors">
                {link.label}
              </Link>
            ))}
          </nav>
          <div className="text-center md:text-right space-y-1">
            <p>
              © {new Date().getFullYear()} {BUSINESS.legalName || 'Clipnera AI'}. All rights reserved.
            </p>
            {(BUSINESS.address || BUSINESS.gstin || BUSINESS.contactEmail) && (
              <p>
                {[BUSINESS.address, BUSINESS.gstin && `GSTIN ${BUSINESS.gstin}`].filter(Boolean).join(' · ')}
                {BUSINESS.contactEmail && (
                  <>
                    {(BUSINESS.address || BUSINESS.gstin) && ' · '}
                    <a href={`mailto:${BUSINESS.contactEmail}`} className="hover:text-white underline underline-offset-2">
                      {BUSINESS.contactEmail}
                    </a>
                  </>
                )}
              </p>
            )}
          </div>
        </div>
      </div>
    </footer>
  );
}
