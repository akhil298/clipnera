import { Disclosure } from '@/components/ui';
import type { ReferralRules as Rules } from '@/lib/types';

const Strong = ({ children }: { children: React.ReactNode }) => <b className="font-semibold text-cn-fg">{children}</b>;

/** The full rules, open by default as in the legacy page: how rewards are earned and why a referral can fail. */
export function ReferralRules({ rules }: { rules: Rules }) {
  const minutes = Math.max(1, Math.round(rules.min_video_seconds / 60));
  return (
    <Disclosure title="Referral rules" variant="card" level={2} defaultOpen>
      <div className="grid gap-5 text-cn-body text-cn-fg-secondary md:grid-cols-2">
        <section className="flex flex-col gap-2">
          <h3 className="text-cn-caption font-semibold text-cn-fg-muted">How rewards are earned</h3>
          <ul className="flex list-disc flex-col gap-1.5 pl-4">
            <li>Your friend must enter your code when they <Strong>create a new account</Strong>. Existing accounts can’t be referred.</li>
            <li>
              They must buy Pro within <Strong>{rules.pro_window_hours} hours</Strong> of signing up. A payment made in time counts once it’s
              approved, if approval comes within {rules.approval_wait_days} days.
            </li>
            <li>
              They must start processing a video of at least <Strong>{minutes} minute{minutes > 1 ? 's' : ''}</Strong> within{' '}
              <Strong>{rules.video_window_hours} hours</Strong> of their Pro starting. It counts once it finishes successfully.
            </li>
            <li>
              You get <Strong>{rules.referrer_pro_credits} + {rules.referrer_video_credits}</Strong> credits; your friend gets{' '}
              <Strong>{rules.referee_pro_credits}</Strong> when they buy Pro. If they never process a video, you keep the first {rules.referrer_pro_credits}.
            </li>
            <li>
              Referral credits <Strong>expire {rules.bonus_expiry_days} days</Strong> after you get them, and are used first when they’d run out
              before your other credits.
            </li>
            <li>You can bring in up to <Strong>{rules.monthly_cap} people a month</Strong>.</li>
          </ul>
        </section>
        <section className="flex flex-col gap-2">
          <h3 className="text-cn-caption font-semibold text-cn-fg-muted">Why a referral can fail</h3>
          <ul className="flex list-disc flex-col gap-1.5 pl-4">
            <li><Strong>Pro not bought in time:</Strong> no Pro payment within {rules.pro_window_hours} hours of sign-up.</li>
            <li><Strong>Payment rejected</Strong>, or <Strong>not approved in time</Strong>.</li>
            <li><Strong>No video in time:</Strong> no video started within {rules.video_window_hours} hours of Pro. Your first reward stays.</li>
            <li><Strong>Payment reversed:</Strong> the Pro payment was refunded, so unspent reward credits are taken back.</li>
            <li><Strong>Under review:</Strong> sign-ups that look like your own second account wait for a manual check before anything is paid.</li>
            <li>Using your own code, or an email that was referred before, isn’t allowed. Credits have no cash value.</li>
          </ul>
        </section>
      </div>
    </Disclosure>
  );
}
