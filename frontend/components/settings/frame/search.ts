import type { SettingsSectionId } from './sections';

/** One place the settings search can send you: a section, a card inside one, or a related page. */
export interface SettingsSearchEntry {
  id: string;
  label: string;
  href: string;
  /** Where it lives, shown under the label ("Plan and billing", "Brand kit page"). */
  context: string;
  /** The section it belongs to; entries of a hidden section are left out. */
  section?: SettingsSectionId;
  /** Words people use for it. Matched by prefix, so "invoice" also covers "invoices". */
  synonyms: string;
}

const S = '/dashboard/settings';

export const SETTINGS_SEARCH_ENTRIES: readonly SettingsSearchEntry[] = [
  { id: 'account', label: 'Account and privacy', href: `${S}/account`, context: 'Section', section: 'account', synonyms: 'profile me personal google privacy' },
  { id: 'profile', label: 'Profile', href: `${S}/account#profile`, context: 'Account and privacy', section: 'account', synonyms: 'name email address photo picture avatar google sign in login' },
  { id: 'legal', label: 'Legal and your data', href: `${S}/account#legal`, context: 'Account and privacy', section: 'account', synonyms: 'terms service privacy policy refund refunds cookie cookies grievance officer complaint dpdp gdpr data' },
  { id: 'delete', label: 'Delete account', href: `${S}/account#delete-account`, context: 'Account and privacy', section: 'account', synonyms: 'remove close erase deactivate cancel account data deletion' },
  { id: 'workspace', label: 'Workspace and team', href: `${S}/workspace`, context: 'Section', section: 'workspace', synonyms: 'team members invite people collaborators organisation organization roles seats share' },
  { id: 'billing', label: 'Plan and billing', href: `${S}/billing`, context: 'Section', section: 'billing', synonyms: 'plan pro free upgrade downgrade subscription renew price pricing card upi pay payment money' },
  { id: 'credits', label: 'Credits and credit packs', href: `${S}/billing`, context: 'Plan and billing', section: 'billing', synonyms: 'credit minutes balance top up topup buy pack usage limits' },
  { id: 'payments', label: 'Payments', href: `${S}/billing`, context: 'Plan and billing', section: 'billing', synonyms: 'receipt invoice bill history transactions utr upi refund' },
  { id: 'notifications', label: 'Notifications', href: `${S}/notifications`, context: 'Section', section: 'notifications', synonyms: 'alerts bell emails mail unsubscribe messages' },
  { id: 'emails', label: 'Account emails', href: `${S}/notifications`, context: 'Notifications', section: 'notifications', synonyms: 'email mail unsubscribe newsletter' },
  { id: 'connections', label: 'Connected accounts', href: `${S}/connections`, context: 'Section', section: 'connections', synonyms: 'youtube instagram social channel publish publishing connect disconnect reconnect integrations' },
  { id: 'brand', label: 'Brand kit', href: '/dashboard/brand-kit', context: 'Brand kit page', synonyms: 'logo colour color colours colors font fonts brand captions caption style watermark channel intro' },
  { id: 'referrals', label: 'Refer and earn', href: '/dashboard/referrals', context: 'Refer and earn page', synonyms: 'referral refer invite friends earn free credits code' },
];

const words = (text: string) => text.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);

/**
 * Entries whose label or synonyms cover every word typed (each as a word prefix),
 * label matches first, then in list order. An empty query returns nothing.
 */
export function searchSettings(query: string, entries: readonly SettingsSearchEntry[] = SETTINGS_SEARCH_ENTRIES): SettingsSearchEntry[] {
  const typed = words(query);
  if (typed.length === 0) return [];
  const scored = entries.flatMap((entry, index) => {
    const label = words(entry.label);
    const all = [...label, ...words(entry.synonyms)];
    if (!typed.every((word) => all.some((term) => term.startsWith(word)))) return [];
    const labelHits = typed.filter((word) => label.some((term) => term.startsWith(word))).length;
    return [{ entry, index, labelHits }];
  });
  return scored.sort((a, b) => b.labelHits - a.labelHits || a.index - b.index).map(({ entry }) => entry);
}
