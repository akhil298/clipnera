'use client';

import { useEffect, useState } from 'react';

export type StudioLayout = 'desktop' | 'tablet' | 'phone';

const PHONE_QUERY = '(max-width: 767px)';
const TABLET_QUERY = '(max-width: 1179px)';

const current = (): StudioLayout =>
  window.matchMedia(PHONE_QUERY).matches ? 'phone' : window.matchMedia(TABLET_QUERY).matches ? 'tablet' : 'desktop';

/**
 * Which Studio arrangement fits the window. Chosen in JS rather than CSS
 * because each arrangement places the one video element somewhere else.
 */
export function useStudioLayout(): StudioLayout {
  const [layout, setLayout] = useState<StudioLayout>('desktop');

  useEffect(() => {
    const queries = [window.matchMedia(PHONE_QUERY), window.matchMedia(TABLET_QUERY)];
    const onChange = () => setLayout(current());
    onChange();
    queries.forEach((q) => q.addEventListener('change', onChange));
    return () => queries.forEach((q) => q.removeEventListener('change', onChange));
  }, []);

  return layout;
}
