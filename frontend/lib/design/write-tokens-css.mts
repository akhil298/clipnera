// Regenerates app/tokens.css from lib/design/tokens.ts: `node lib/design/write-tokens-css.mts`.
import { writeFileSync } from 'node:fs';

import { renderTokensCss } from './tokens.ts';

writeFileSync(new URL('../../app/tokens.css', import.meta.url), renderTokensCss());
