'use client';

import { History, RotateCw, TriangleAlert, WifiOff } from 'lucide-react';
import Link from 'next/link';
import type { ReactNode } from 'react';

import { cx, focusRing } from '@/lib/design/styles';

import { shortOfCreditsText } from './composer-logic';
import type { EditorComposerState } from './useEditorComposer';

const BILLING_PATH = '/dashboard/settings/billing';

const actionClasses = cx('shrink-0 rounded-cn-xs font-semibold text-cn-fg underline-offset-2 hover:underline', focusRing);

function Line({ icon, tone = 'muted', children, action }: { icon: ReactNode; tone?: 'muted' | 'danger'; children: ReactNode; action?: ReactNode }) {
  return (
    <p className={cx('flex items-start gap-2 px-1 text-cn-caption', tone === 'danger' ? 'text-cn-danger-text' : 'text-cn-fg-secondary')}>
      <span aria-hidden className="mt-0.5 inline-flex shrink-0 [&_svg]:size-3.5">
        {icon}
      </span>
      <span className="min-w-0 flex-1">{children}</span>
      {action}
    </p>
  );
}

const addCredits = (
  <Link href={BILLING_PATH} className={actionClasses}>
    Add credits
  </Link>
);

/**
 * The one line under the box (07 §6.1), most important first: viewing an older version,
 * offline, a send that didn't arrive, not enough credits, a queue or Stop that failed.
 */
export function ComposerNotice({ state }: { state: EditorComposerState }) {
  const { readOnly, online, failure, estimate, shortOfCredits, actionError } = state;

  const line = (() => {
    if (readOnly)
      return (
        <Line
          icon={<History />}
          action={
            <button type="button" onClick={state.backToLatest} className={actionClasses}>
              Back to latest
            </button>
          }
        >
          Viewing an earlier version
        </Line>
      );
    if (!online)
      return (
        <Line icon={<WifiOff />}>
          You&apos;re offline. Your text is kept; send when you&apos;re back.
        </Line>
      );
    if (failure)
      return (
        <Line
          icon={<TriangleAlert />}
          tone="danger"
          action={
            failure.kind === 'credits' ? (
              addCredits
            ) : (
              <button type="button" onClick={state.retry} className={cx(actionClasses, 'inline-flex items-center gap-1')}>
                <RotateCw aria-hidden className="size-3.5" />
                Retry
              </button>
            )
          }
        >
          {failure.text}
        </Line>
      );
    if (shortOfCredits && estimate)
      return (
        <Line icon={<TriangleAlert />} tone="danger" action={addCredits}>
          {shortOfCreditsText(estimate)}
        </Line>
      );
    if (actionError)
      return (
        <Line
          icon={<TriangleAlert />}
          tone="danger"
          action={
            <button type="button" onClick={state.dismissActionError} className={actionClasses}>
              Dismiss
            </button>
          }
        >
          {actionError}
        </Line>
      );
    return null;
  })();

  return (
    <div role="status" aria-live="polite">
      {line}
    </div>
  );
}
