'use client';

import { useQuery } from '@tanstack/react-query';

import { getConnections } from '@/lib/api/social';
import { useFlag } from '@/lib/flags/useFlag';
import { socialKeys } from '@/lib/query/keys/social';

import { SETTINGS_SECTIONS, type SettingsSection } from './sections';

/**
 * The sections this person sees. Connected accounts shows while social publishing
 * is on or they still have accounts, so turning the feature off never stops anyone
 * disconnecting (parity with the legacy `useSocialTabVisible`).
 */
export function useSettingsSections(): readonly SettingsSection[] {
  const publishing = useFlag('social_publishing');
  const hasAccounts = useQuery({
    queryKey: socialKeys.connections(),
    queryFn: ({ signal }) => getConnections(signal),
    enabled: !publishing,
    select: (data) => data.accounts.length > 0,
  }).data;
  const showConnections = publishing || hasAccounts === true;
  return showConnections ? SETTINGS_SECTIONS : SETTINGS_SECTIONS.filter((item) => item.id !== 'connections');
}
