import { Crown } from 'lucide-react';
import Link from 'next/link';
import type { ReactNode } from 'react';

import { Avatar, Badge } from '@/components/ui';
import type { UserProfile } from '@/lib/api/me';
import { cx, focusRing } from '@/lib/design/styles';
import { formatDate } from '@/lib/utils/dates';

import { sectionById, SettingsCard } from '../frame';

import { KeyValues } from './KeyValues';

/** "google" → "Google", "pro" → "Pro". */
const capitalise = (word: string) => word.charAt(0).toUpperCase() + word.slice(1);

/**
 * Who is signed in. Everything here comes from Google, so it is shown as text, not
 * as disabled inputs. Member since and Age confirmed wait for L-API-5.
 */
export function ProfileCard({ me }: { me: UserProfile }) {
  const pro = me.plan !== 'free';
  const facts: Array<{ label: string; value: ReactNode }> = [];
  if (me.providers.length > 0) facts.push({ label: 'Signed in with', value: me.providers.map(capitalise).join(', ') });
  if (pro && me.plan_expires_at) {
    facts.push({
      label: 'Plan',
      value: (
        <Link href={sectionById('billing').href} className={cx('rounded-cn-xs text-cn-accent-text underline underline-offset-2', focusRing)}>
          {capitalise(me.plan)} until {formatDate(me.plan_expires_at)}
        </Link>
      ),
    });
  }

  return (
    <SettingsCard
      id="profile"
      title="Profile"
      description="Your name, email and picture come from your Google account. Change them in Google and they update here at your next sign-in."
    >
      <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:gap-4">
        <Avatar name={me.name} src={me.avatar_url ?? undefined} size={40} />
        <div className="min-w-0 flex-1">
          <p className="break-words text-cn-body font-semibold text-cn-fg">{me.name}</p>
          <p className="break-all text-cn-label text-cn-fg-secondary">{me.email}</p>
        </div>
        <Badge tone={pro ? 'accent' : 'neutral'} icon={pro ? <Crown /> : undefined}>
          {capitalise(me.plan)} plan
        </Badge>
      </div>
      {facts.length > 0 && <KeyValues className="mt-4" items={facts} />}
    </SettingsCard>
  );
}
