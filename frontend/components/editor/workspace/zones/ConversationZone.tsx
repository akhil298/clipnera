'use client';

/**
 * Z4 conversation slot. Filled by E3 (composer), E4a (thread, run wiring) and E4b (cards). Only
 * rendered when `useEditor().features.conversation` is on.
 *
 * Props contract (stable):
 * - `placement`:
 *   - `side`: full-height right zone (≥ 1024). Thread scrolls; queue above the composer; composer pinned at the bottom.
 *   - `drawer`: the thread only, in the right Chat drawer at 768–1023 (the composer is the `dock`).
 *   - `dock`: the composer only, a full-width docked bar under the preview at 768–1023.
 *   - `phone`: the Chat tab; thread plus composer pinned above the safe area.
 * From `useEditor()`: `runs`, `selection` (`chipsFor`), `doc`, `sim` (dev: call `sim.start(scenario)`
 * on send when set), `promptRef` (attach to the composer's textarea so ⌘K and / focus it),
 * `connection` (disable Send while offline), `openExport`.
 */
import { MessageSquare } from 'lucide-react';

import { ZoneNote } from '../Zone';

export type ConversationPlacement = 'side' | 'drawer' | 'dock' | 'phone';

export interface ConversationZoneProps {
  placement: ConversationPlacement;
}

export function ConversationZone({ placement }: ConversationZoneProps) {
  if (placement === 'dock') {
    return <p className="flex h-11 items-center px-3 text-cn-label text-cn-fg-muted">Describe an edit to this video</p>;
  }
  return (
    <ZoneNote
      icon={<MessageSquare />}
      title="Talk to Clipnera"
      description="Ask for an edit in plain words. Each change lands on the timeline and saves a version."
    />
  );
}
