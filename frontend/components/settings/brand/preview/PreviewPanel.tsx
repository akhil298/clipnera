'use client';

import { Disclosure } from '@/components/ui';

import { BrandPreview, type BrandPreviewKit } from './BrandPreview';

/**
 * Where the preview sits at each width (screens/03 §16.1): beside the form and
 * sticky from 1024; above it at 240 px on tablets; a 160 px phone in an open
 * "Preview" disclosure on phones. Only one copy is ever displayed.
 */
export function PreviewPanel({ kit }: { kit: BrandPreviewKit }) {
  return (
    <aside aria-label="Brand kit preview" className="min-w-0 lg:col-span-5">
      <div className="sm:hidden">
        <Disclosure title="Preview" defaultOpen variant="card" level={2}>
          <BrandPreview kit={kit} size="sm" />
        </Disclosure>
      </div>
      <div className="hidden sm:block lg:hidden">
        <BrandPreview kit={kit} size="md" />
      </div>
      <div className="hidden lg:sticky lg:top-20 lg:block">
        <BrandPreview kit={kit} size="lg" />
      </div>
    </aside>
  );
}
