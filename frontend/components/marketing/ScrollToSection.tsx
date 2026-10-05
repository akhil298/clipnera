'use client';

import { useEffect } from 'react';

/** Lands the page on one section without changing the URL (`/editor` opens at Editing). */
export function ScrollToSection({ id }: { id: string }) {
  useEffect(() => {
    if (!window.location.hash) document.getElementById(id)?.scrollIntoView({ block: 'start' });
  }, [id]);
  return null;
}
