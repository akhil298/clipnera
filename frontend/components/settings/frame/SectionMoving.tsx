import { ExternalLink } from 'lucide-react';

import { buttonClasses, EmptyState } from '@/components/ui';

import { classicHref, sectionById, type SettingsSectionId } from './sections';

/**
 * Hand-over page for a section whose new screen isn't in yet (U2–U5 replace it).
 * Everything still works in the classic design, so this links there instead of dead-ending.
 */
export function SectionMoving({ id }: { id: SettingsSectionId }) {
  const item = sectionById(id);
  return (
    <div className="rounded-cn-lg border border-cn-border bg-cn-surface">
      <EmptyState
        level={2}
        icon={item.icon}
        title={`${item.label} is moving here`}
        description={`I’m rebuilding this page. Until it’s ready, everything in ${item.label} still works in the classic design. Opening it switches this browser to the classic design.`}
        action={
          <a href={classicHref(item)} className={buttonClasses({ variant: 'secondary' })}>
            <ExternalLink aria-hidden className="mr-2 size-4" />
            Open in the classic design
          </a>
        }
      />
    </div>
  );
}
