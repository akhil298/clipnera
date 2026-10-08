import { Gift } from 'lucide-react';

import { buttonClasses, Card, CopyField, ProgressBar } from '@/components/ui';
import type { MyReferralsResponse } from '@/lib/types';

/** The caller's code and link, ways to share them, and this month's allowance. */
export function ShareCard({ data }: { data: MyReferralsResponse }) {
  const { rules } = data;
  const total = rules.referrer_pro_credits + rules.referrer_video_credits;
  const shareText = data.code && data.share_url ? `Try Clipnera with my code ${data.code}: ${data.share_url}` : '';

  return (
    <Card padding="lg" className="flex flex-col gap-4 border-cn-accent/30">
      <p className="inline-flex items-center gap-1.5 text-cn-label font-semibold text-cn-accent-text">
        <Gift aria-hidden className="size-4" /> Refer and earn
      </p>
      <h1 className="text-cn-title-lg font-bold text-cn-fg">
        Earn <span className="text-cn-accent-text">{total} credits</span> for every friend who goes Pro and makes their first clips
      </h1>
      <p className="text-cn-body text-cn-fg-secondary">Your friend gets {rules.referee_pro_credits} bonus credits when they buy Pro.</p>

      {data.enabled && data.code && data.share_url ? (
        <>
          <CopyField label="Your code" value={data.code} />
          <CopyField label="Your link" value={data.share_url} />
          <div className="flex flex-wrap gap-2">
            <a
              href={`https://wa.me/?text=${encodeURIComponent(shareText)}`}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonClasses({ variant: 'secondary', size: 'sm' })}
            >
              Share on WhatsApp
            </a>
            <a
              href={`https://x.com/intent/post?text=${encodeURIComponent(shareText)}`}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonClasses({ variant: 'secondary', size: 'sm' })}
            >
              Post on X
            </a>
          </div>
          <ProgressBar
            label="Referrals used this month"
            value={Math.min(data.used_this_month, rules.monthly_cap)}
            max={Math.max(rules.monthly_cap, 1)}
            valueText={`${data.used_this_month} of ${rules.monthly_cap}`}
            size="sm"
          />
        </>
      ) : (
        <p className="rounded-cn-md border border-cn-border bg-cn-bg p-3 text-cn-body text-cn-fg-secondary">
          Referrals are paused right now. Referrals already in progress still finish and pay out.
        </p>
      )}
    </Card>
  );
}
