// Short-form formats the AI cuts clips as: mirrors RECIPES in backend/formats/taxonomy.py.

export type ContentFormat =
  | 'talking_head'
  | 'yap'
  | 'split_screen'
  | 'green_screen'
  | 'voice_over'
  | 'broll'
  | 'listicle'
  | 'ranking'
  | 'reaction'
  | 'screen_share'
  | 'clone';

/** Recipe.overlay: what the burner draws over a clip of each format. */
export type FormatOverlay = 'none' | 'list_counter' | 'rank_board';

export const CONTENT_FORMAT_LABELS: Record<ContentFormat, string> = {
  talking_head: 'Talking head',
  yap: 'Yap',
  split_screen: 'Split screen',
  green_screen: 'Green screen',
  voice_over: 'Voice over',
  broll: 'B-roll',
  listicle: 'Listicle',
  ranking: 'Ranking',
  reaction: 'Reaction',
  screen_share: 'Screen share',
  clone: 'Clone',
};

export const asContentFormat = (value: string | null | undefined): ContentFormat | null =>
  value && value in CONTENT_FORMAT_LABELS ? (value as ContentFormat) : null;

export const formatOverlay = (format: ContentFormat | null | undefined): FormatOverlay =>
  format === 'listicle' ? 'list_counter' : format === 'ranking' ? 'rank_board' : 'none';
