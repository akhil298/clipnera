'use client';

import { FolderOpen, House, Library, Palette, Send } from 'lucide-react';
import type { ReactNode } from 'react';

import { useFlag } from '@/lib/flags/useFlag';

export type NavId = 'home' | 'projects' | 'library' | 'publish' | 'brand';

export interface NavItem {
  id: NavId;
  label: string;
  href: string;
  icon: ReactNode;
}

export const HOME_HREF = '/dashboard';
export const NEW_VIDEO_HREF = '/dashboard/upload';
export const SETTINGS_HREF = '/dashboard/settings';
export const BILLING_HREF = '/dashboard/settings/billing';
export const ADMIN_HREF = '/admin';

/** The sidebar's destinations, at most five (07 §5.2). Publish shows only with social publishing on. */
export function useNavItems(): NavItem[] {
  const publishing = useFlag('social_publishing');
  const items: Array<NavItem | false> = [
    { id: 'home', label: 'Home', href: HOME_HREF, icon: <House /> },
    { id: 'projects', label: 'Projects', href: '/dashboard/projects', icon: <FolderOpen /> },
    { id: 'library', label: 'Library', href: '/dashboard/library', icon: <Library /> },
    publishing && { id: 'publish', label: 'Publish', href: '/dashboard/scheduler', icon: <Send /> },
    { id: 'brand', label: 'Brand kit', href: '/dashboard/brand-kit', icon: <Palette /> },
  ];
  return items.filter((item): item is NavItem => item !== false);
}

/** First path segment under /dashboard → the nav item it belongs to. Reels live in Projects; analytics in Publish. */
const SECTION: Record<string, NavId> = {
  projects: 'projects',
  folders: 'projects',
  reels: 'projects',
  library: 'library',
  scheduler: 'publish',
  analytics: 'publish',
  'brand-kit': 'brand',
};

/** Public URL path (with or without the internal `/v2` prefix) → path segments under `/dashboard`, or null outside it. */
export function dashboardSegments(pathname: string): string[] | null {
  const parts = pathname.replace(/^\/v2(?=\/)/, '').split('/').filter(Boolean);
  return parts[0] === 'dashboard' ? parts.slice(1) : null;
}

export function activeNavId(pathname: string): NavId | null {
  const segments = dashboardSegments(pathname);
  if (!segments) return null;
  if (segments.length === 0) return 'home';
  return SECTION[segments[0]] ?? null;
}
