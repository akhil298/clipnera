'use client';

/**
 * The version switcher beside the project name in the top bar (07 §5.4: "name ▾ (version)"). Filled
 * by V1 with a Menu of recent versions. Keep it ≤ 28 px tall (`h-7`).
 *
 * Props contract (stable): none. From `useEditor()`: `doc` (`selectVersion`, `preview`), `history`.
 */
import { selectVersion, useDoc } from '@/lib/editor/store';

import { useEditor } from '../context';

export function VersionSwitcherZone() {
  const { doc } = useEditor();
  const version = useDoc(doc, selectVersion);
  if (version === null) return null;
  return <span className="shrink-0 font-cn-mono text-cn-caption tabular-nums text-cn-fg-muted">v{version}</span>;
}
