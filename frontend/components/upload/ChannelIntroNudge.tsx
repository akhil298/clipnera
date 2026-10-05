'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';

import { InlineAlert, buttonClasses } from '@/components/ui';
import { getCreatorIntro } from '@/lib/api/pipeline';
import { usePersistentState } from '@/lib/design/usePersistentState';
import { uploadKeys } from '@/lib/query/keys/upload';

const INTRO_HREF = '/dashboard/brand-kit#channel-intro';

/** Once per channel, before a Pro run: make the intro that plays before every export (kept from the legacy flow). */
export function ChannelIntroNudge({ allowed }: { allowed: boolean }) {
  const [dismissed, setDismissed] = usePersistentState('cn.upload.channelIntroNudgeDismissed', false);
  const intro = useQuery({
    queryKey: uploadKeys.creatorIntro(),
    queryFn: ({ signal }) => getCreatorIntro(signal),
    enabled: allowed && !dismissed,
    staleTime: 5 * 60_000,
    retry: false,
  });
  const needsIntro = intro.isSuccess && (!intro.data || intro.data.status === 'draft' || intro.data.status === 'failed');
  if (!allowed || dismissed || !needsIntro) return null;

  return (
    <InlineAlert
      tone="neutral"
      title="Add your channel intro first?"
      onDismiss={() => setDismissed(true)}
      action={
        <Link href={INTRO_HREF} className={buttonClasses({ variant: 'secondary', size: 'sm' })}>
          Create intro
        </Link>
      }
    >
      Your name, what the channel is about and a Subscribe tap, played once at the start of each export. Made once.
    </InlineAlert>
  );
}
