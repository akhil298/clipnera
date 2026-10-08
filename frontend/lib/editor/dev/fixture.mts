/** The shared backend Timeline fixture, normalised, for the editor store tests. Test-only. */
import { readFileSync } from 'node:fs';

import { normalise, type Timeline } from '../timeline.ts';

const fixtures = JSON.parse(
  readFileSync(new URL('../../../../backend/editor/fixtures/timeline_ops.json', import.meta.url), 'utf8'),
) as { base: unknown };

export const baseTimeline = (): Timeline => normalise(fixtures.base);
