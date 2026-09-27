'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';

const NAV: { href: string; label: string }[] = [
  { href: '/admin/overview', label: 'Overview' },
  { href: '/admin/users', label: 'Users' },
  { href: '/admin/payments', label: 'Payments' },
  { href: '/admin/credits', label: 'Credits' },
  { href: '/admin/social', label: 'Social' },
  { href: '/admin/usage', label: 'AI usage' },
  { href: '/admin/broll', label: 'B-roll library' },
  { href: '/admin/features', label: 'Features' },
];

interface AdminLayoutProps {
  title: string;
  subtitle: string;
  /** Rendered at the right of the header, e.g. a search box. */
  actions?: React.ReactNode;
  children: React.ReactNode;
}

/** Page frame and section nav shared by every admin page. Access is checked
 * by AdminGate in app/admin/layout.tsx before any admin page mounts. */
export function AdminLayout({ title, subtitle, actions, children }: AdminLayoutProps) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 font-['Plus_Jakarta_Sans',sans-serif]">
      <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <Link href="/dashboard" className="inline-flex items-center gap-1 text-xs text-neutral-400 hover:text-white">
              <ArrowLeft className="w-3.5 h-3.5" />
              Dashboard
            </Link>
            <h1 className="text-2xl font-bold text-white font-['Syne',sans-serif] mt-1">{title}</h1>
            <p className="text-xs text-neutral-400">{subtitle}</p>
          </div>
          {actions}
        </div>

        <nav className="flex gap-4 border-b border-neutral-800">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`pb-2 -mb-px text-sm font-bold border-b-2 transition-colors ${
                pathname === item.href
                  ? 'border-amber-400 text-white'
                  : 'border-transparent text-neutral-400 hover:text-white'
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        {children}
      </div>
    </div>
  );
}
