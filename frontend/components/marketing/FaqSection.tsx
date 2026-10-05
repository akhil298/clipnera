import { ChevronDown } from 'lucide-react';

import { cx, focusRing } from '@/lib/design/styles';
import { FAQS } from '@/lib/marketing/content';

import { Section } from './Section';

/** Native disclosure rows: server-rendered, keyboard and screen-reader ready, and findable with Ctrl+F. */
export function FaqSection() {
  return (
    <Section id="faq" title="Straight answers" width="narrow">
      <div className="divide-y divide-cn-border border-y border-cn-border">
        {FAQS.map((faq, index) => (
          <details key={faq.q} open={index === 0} className="group py-4">
            <summary
              className={cx(
                'flex cursor-pointer list-none items-center justify-between gap-4 rounded-cn-xs text-cn-body-lg font-semibold text-cn-fg hover:text-cn-fg-secondary [&::-webkit-details-marker]:hidden',
                focusRing,
              )}
            >
              <h3>{faq.q}</h3>
              <ChevronDown aria-hidden className="size-4 shrink-0 text-cn-fg-muted group-open:rotate-180 motion-safe:transition-transform motion-safe:duration-cn-base" />
            </summary>
            <p className="mt-2 max-w-prose text-cn-body text-cn-fg-secondary">{faq.a}</p>
          </details>
        ))}
      </div>
    </Section>
  );
}
