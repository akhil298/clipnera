import { Bell, CreditCard, Plug, User, Users } from 'lucide-react';
import type { ReactNode } from 'react';

export const SETTINGS_HREF = '/dashboard/settings';

export type SettingsSectionId = 'account' | 'workspace' | 'billing' | 'notifications' | 'connections';

/** The legacy SettingsView tab (`?tab=`) that holds each section's controls today. */
type LegacyTab = 'account' | 'billing' | 'social' | 'team';

export interface SettingsSection {
  id: SettingsSectionId;
  label: string;
  /** One line for the phone list. */
  description: string;
  href: string;
  icon: ReactNode;
  legacyTab: LegacyTab;
}

const section = (id: SettingsSectionId, label: string, description: string, icon: ReactNode, legacyTab: LegacyTab): SettingsSection => ({
  id,
  label,
  description,
  href: `${SETTINGS_HREF}/${id}`,
  icon,
  legacyTab,
});

/** In order (screens/03 §9.1). Legacy `social` and `team` URLs redirect to `connections` and `workspace`. */
export const SETTINGS_SECTIONS: readonly SettingsSection[] = [
  section('account', 'Account and privacy', 'Profile, legal and deleting your account', <User />, 'account'),
  section('workspace', 'Workspace and team', 'Your workspace and who can work in it', <Users />, 'team'),
  section('billing', 'Plan and billing', 'Plan, credits, credit packs and payments', <CreditCard />, 'billing'),
  // Account emails sit on the legacy Profile tab.
  section('notifications', 'Notifications', 'What Clipnera tells you, and where', <Bell />, 'account'),
  section('connections', 'Connected accounts', 'YouTube and Instagram accounts you publish to', <Plug />, 'social'),
];

export function sectionById(id: SettingsSectionId): SettingsSection {
  return SETTINGS_SECTIONS.find((item) => item.id === id) ?? SETTINGS_SECTIONS[0];
}

/** The section a settings URL is in, or null on `/dashboard/settings` itself. */
export function sectionForPath(pathname: string): SettingsSection | null {
  const id = pathname.slice(SETTINGS_HREF.length + 1).split('/')[0];
  return SETTINGS_SECTIONS.find((item) => item.id === id) ?? null;
}

/** Opens a section in the classic design (sets the per-browser override, then redirects). */
export function classicHref(item: SettingsSection): string {
  const next = `${SETTINGS_HREF}?tab=${item.legacyTab}`;
  return `/api/ui/override?mode=classic&next=${encodeURIComponent(next)}`;
}
