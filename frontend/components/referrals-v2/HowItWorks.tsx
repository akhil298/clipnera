import { Card, CardHeader } from '@/components/ui';
import type { ReferralRules } from '@/lib/types';

/** The three milestones and what each one pays. */
export function HowItWorks({ rules }: { rules: ReferralRules }) {
  const steps = [
    { title: 'Your friend signs up with your code', detail: 'They enter it on the welcome form, or open your link.', earn: [] },
    {
      title: `They buy Pro within ${rules.pro_window_hours} hours`,
      detail: 'Counted from when they sign up.',
      earn: [`you +${rules.referrer_pro_credits}`, `them +${rules.referee_pro_credits}`],
    },
    {
      title: `They process a video within ${rules.video_window_hours} hours of Pro`,
      detail: 'Paid when that video finishes processing.',
      earn: [`you +${rules.referrer_video_credits}`],
    },
  ];
  return (
    <Card padding="lg" className="flex flex-col gap-4">
      <CardHeader title="How it works" level={2} />
      <ol className="flex flex-col gap-3">
        {steps.map((step, index) => (
          <li key={step.title} className="grid grid-cols-[auto_1fr_auto] items-start gap-3">
            <span aria-hidden className="grid size-7 place-items-center rounded-cn-full border border-cn-border text-cn-caption font-semibold text-cn-fg-secondary">
              {index + 1}
            </span>
            <div>
              <p className="text-cn-body font-semibold text-cn-fg">{step.title}</p>
              <p className="text-cn-caption text-cn-fg-muted">{step.detail}</p>
            </div>
            <span className="flex flex-col items-end font-cn-mono text-cn-caption text-cn-accent-text">
              {step.earn.map((line) => (
                <span key={line}>{line}</span>
              ))}
            </span>
          </li>
        ))}
      </ol>
      <p className="text-cn-caption text-cn-fg-muted">Bonus credits expire {rules.bonus_expiry_days} days after you get them.</p>
    </Card>
  );
}
