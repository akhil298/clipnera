import type { TextItem } from '@timeline'
import type { PreviewText } from '../../shared/api'

/** Which of the renderer's three title kinds a text item draws as (brain/render_adapter.py to_reel). */
export function textKind(item: TextItem): PreviewText['kind'] {
  if (item.at === 0 && item.transform.y < 0.45) return 'hook'
  return item.transform.y > 0.6 ? 'line' : 'pop'
}
