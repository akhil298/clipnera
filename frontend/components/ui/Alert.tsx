import { AlertTriangle, CircleAlert, CircleCheck, Info, X } from 'lucide-react';
import type { ReactNode } from 'react';

import { cx } from '@/lib/design/styles';

import { IconButton } from './IconButton';

export type AlertTone = 'neutral' | 'info' | 'warning' | 'danger' | 'success';

const TONE: Record<AlertTone, { box: string; strip: string; icon: ReactNode; word: string }> = {
  neutral: { box: 'border-cn-border bg-cn-surface', strip: 'bg-cn-surface', icon: <Info className="text-cn-fg-muted" />, word: 'Note' },
  info: { box: 'border-cn-info/30 bg-cn-info-subtle', strip: 'bg-cn-info-subtle', icon: <Info className="text-cn-info-text" />, word: 'Info' },
  warning: {
    box: 'border-cn-accent/30 bg-cn-accent-subtle',
    strip: 'bg-cn-accent-subtle',
    icon: <AlertTriangle className="text-cn-accent-text" />,
    word: 'Warning',
  },
  danger: { box: 'border-cn-danger/30 bg-cn-danger-subtle', strip: 'bg-cn-danger-subtle', icon: <CircleAlert className="text-cn-danger-text" />, word: 'Error' },
  success: {
    box: 'border-cn-success/30 bg-cn-success-subtle',
    strip: 'bg-cn-success-subtle',
    icon: <CircleCheck className="text-cn-success-text" />,
    word: 'Done',
  },
};

interface AlertContentProps {
  tone?: AlertTone;
  title?: ReactNode;
  children?: ReactNode;
  /** One action (a small Button or a link). Errors: the fix, or Try again if retryable. */
  action?: ReactNode;
  /** Shows a close button. Omit for notices the person cannot dismiss. */
  onDismiss?: () => void;
  /** `alert` for an error that just happened, `status` for a state change; omit for standing notices. */
  live?: 'alert' | 'status';
  className?: string;
}

function Body({ tone, title, children }: { tone: AlertTone; title?: ReactNode; children?: ReactNode }) {
  return (
    <>
      <span aria-hidden className="mt-0.5 inline-flex shrink-0 [&_svg]:size-4">
        {TONE[tone].icon}
      </span>
      <div className="min-w-0 flex-1 space-y-0.5 text-cn-body">
        <span className="sr-only">{TONE[tone].word}: </span>
        {title && <p className="font-semibold text-cn-fg">{title}</p>}
        {children && <div className="text-cn-fg-secondary">{children}</div>}
      </div>
    </>
  );
}

/**
 * A message that stays in place inside the content: a blocked action, a
 * pending payment, a plan limit. Not a toast. Errors follow 02 §7.3: what
 * happened, what is safe, one action.
 */
export function InlineAlert({ tone = 'neutral', title, children, action, onDismiss, live, className }: AlertContentProps) {
  return (
    <div role={live} className={cx('flex flex-wrap items-start gap-3 rounded-cn-lg border p-3 sm:flex-nowrap', TONE[tone].box, className)}>
      <Body tone={tone} title={title}>
        {children}
      </Body>
      {action && <div className="flex shrink-0 flex-wrap items-center gap-2">{action}</div>}
      {onDismiss && <IconButton label="Dismiss" icon={<X />} size="sm" tooltip={false} onClick={onDismiss} className="-my-1 -mr-1" />}
    </div>
  );
}

export interface BannerProps extends AlertContentProps {
  /** Stick to the top of the scroll area under the header (`z-cn-banner`). */
  sticky?: boolean;
}

/**
 * A full-width strip under the top bar for app-wide notices: offline, payment
 * failed, maintenance, an expiring connection. One at a time; the most severe wins.
 */
export function Banner({ tone = 'info', title, children, action, onDismiss, live, sticky = false, className }: BannerProps) {
  return (
    <div
      role={live ?? 'region'}
      aria-label={live ? undefined : 'Notice'}
      className={cx('border-b border-cn-border', TONE[tone].strip, sticky && 'sticky top-0 z-cn-banner', className)}
    >
      <div className="mx-auto flex max-w-screen-xl flex-wrap items-start gap-3 px-4 py-2.5 sm:flex-nowrap sm:items-center sm:px-6 lg:px-8">
        <Body tone={tone} title={title}>
          {children}
        </Body>
        {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
        {onDismiss && <IconButton label="Dismiss notice" icon={<X />} size="sm" tooltip={false} onClick={onDismiss} />}
      </div>
    </div>
  );
}
