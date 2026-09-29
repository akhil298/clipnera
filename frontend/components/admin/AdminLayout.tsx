'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ArrowLeft, Clapperboard, Coins, Cpu, CreditCard, LayoutDashboard, Share2, ToggleRight, Users } from 'lucide-react';
import { LogoMark } from '@/components/ui/LogoMark';

const NAV: { href: string; label: string; icon: React.FC<{ className?: string }> }[] = [
  { href: '/admin/overview', label: 'Overview', icon: LayoutDashboard },
  { href: '/admin/users', label: 'Users', icon: Users },
  { href: '/admin/payments', label: 'Payments', icon: CreditCard },
  { href: '/admin/credits', label: 'Credits', icon: Coins },
  { href: '/admin/social', label: 'Social', icon: Share2 },
  { href: '/admin/usage', label: 'AI usage', icon: Cpu },
  { href: '/admin/broll', label: 'B-roll library', icon: Clapperboard },
  { href: '/admin/features', label: 'Features', icon: ToggleRight },
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
  const isActive = (href: string) => pathname === href || pathname?.startsWith(`${href}/`);

  return (
    <div className="min-h-[100dvh] bg-neutral-950 text-neutral-100 lg:flex">
      {/* Desktop: the same side navigation as the app */}
      <aside className="hidden lg:flex flex-col w-60 shrink-0 h-[100dvh] sticky top-0 border-r border-neutral-800/80 p-4 gap-4">
        <Link href="/dashboard" className="flex items-center gap-2.5">
          <LogoMark />
          <span className="font-extrabold text-[17px] tracking-tight">
            Clip<span className="text-amber-400">nera</span>
          </span>
          <span className="px-1.5 py-px text-[9px] font-bold rounded bg-violet-500/15 text-violet-300 border border-violet-500/30 uppercase">Admin</span>
        </Link>
        <nav aria-label="Admin" className="flex-1 space-y-0.5">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={isActive(href) ? 'page' : undefined}
              className={`relative flex items-center gap-3 px-3 py-2 rounded-lg text-[13px] transition-colors ${
                isActive(href) ? 'bg-neutral-800/80 text-white font-semibold' : 'text-neutral-400 hover:text-white hover:bg-neutral-900 font-medium'
              }`}
            >
              {isActive(href) && <span className="absolute -left-4 top-2 bottom-2 w-[3px] rounded-r bg-amber-400" aria-hidden="true" />}
              <Icon className={`w-4 h-4 ${isActive(href) ? 'text-amber-400' : ''}`} />
              {label}
            </Link>
          ))}
        </nav>
        <Link href="/dashboard" className="flex items-center gap-2 px-3 py-2 rounded-lg text-[13px] font-semibold text-neutral-300 hover:text-white hover:bg-neutral-900">
          <ArrowLeft className="w-4 h-4" /> Back to the app
        </Link>
      </aside>

      <div className="flex-1 min-w-0">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-8 space-y-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="min-w-0 space-y-1.5">
              <Link href="/dashboard" className="lg:hidden inline-flex items-center gap-1 text-xs font-semibold text-neutral-400 hover:text-white">
                <ArrowLeft className="w-3.5 h-3.5" /> Back to the app
              </Link>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">{title}</h1>
              <p className="text-sm text-neutral-400">{subtitle}</p>
            </div>
            {actions}
          </div>

          {/* Phones and tablets: sections as scrolling tabs */}
          <nav aria-label="Admin" className="lg:hidden -mx-4 px-4 sm:mx-0 sm:px-0 flex gap-1 overflow-x-auto [scrollbar-width:none]">
            {NAV.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                aria-current={isActive(href) ? 'page' : undefined}
                className={`shrink-0 flex items-center gap-1.5 h-9 px-3 rounded-xl text-xs font-semibold border transition-colors ${
                  isActive(href) ? 'bg-neutral-800 border-neutral-700 text-white' : 'border-neutral-800 text-neutral-400 hover:text-white'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive(href) ? 'text-amber-400' : ''}`} />
                {label}
              </Link>
            ))}
          </nav>

          {children}
        </div>
      </div>
    </div>
  );
}
