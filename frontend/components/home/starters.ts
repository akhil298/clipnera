/**
 * Words that fill the composer. None of them sends: the person reads, edits,
 * then presses send (01 §4, 07 §5.3).
 */

/** What the composer holds once a link is attached and nothing was typed: the default run. */
export const DEFAULT_INSTRUCTION = 'Find the best moments';

export const SUGGESTIONS = {
  noVideo: ['Find the 5 best moments', 'Clips under 30 seconds', 'Only the funny parts', 'Hinglish captions'],
  withVideo: ['Find the 5 best moments', 'Clips under 45 seconds with captions', 'Pull every question the guest answers', 'Keep the swearing out'],
} as const;

export interface Starter {
  id: string;
  title: string;
  prompt: string;
}

/**
 * Starters phrased as intents over Clipnera's 11 content formats
 * (backend/formats taxonomy). Clipnera still picks the format from the footage;
 * a starter only says what to look for.
 */
export const STARTERS: readonly Starter[] = [
  { id: 'talking_head', title: 'Talking-head shorts', prompt: 'Cut tight talking-head shorts with captions on every word' },
  { id: 'yap', title: 'Hot takes', prompt: 'Find my strongest opinions and keep them punchy' },
  { id: 'listicle', title: 'Tips as a list', prompt: 'Turn the tips in this video into numbered list clips' },
  { id: 'ranking', title: 'Rankings', prompt: 'Pull out every ranking or top pick and count it down' },
  { id: 'reaction', title: 'Reactions', prompt: 'Find the moments where I react to something on screen' },
  { id: 'screen_share', title: 'Screen walkthroughs', prompt: 'Clip the screen-share parts where I show how something works' },
  { id: 'voice_over', title: 'Voice-over stories', prompt: 'Make story clips with my voice over matching footage' },
  { id: 'broll', title: 'Explainers with B-roll', prompt: 'Explain the key ideas with B-roll cutaways' },
  { id: 'split_screen', title: 'Conversations', prompt: 'Clip the back-and-forth with both speakers on screen' },
  { id: 'green_screen', title: 'Green screen', prompt: 'Put me in front of the thing I’m talking about' },
  { id: 'clone', title: 'Skits', prompt: 'Find the skits where I play more than one character' },
];

/** The one question asked before credits are spent, when the prompt doesn't already say how long (Perplexity rec. 4). */
export const LENGTH_CHOICES = [
  { id: 'short', label: 'Under 30 seconds', description: 'Quick hooks for Shorts and Reels', min: 15, max: 30 },
  { id: 'medium', label: '30 to 45 seconds', description: 'One idea, told fully', min: 30, max: 45 },
  { id: 'long', label: '45 to 60 seconds', description: 'Room for a story', min: 45, max: 60 },
] as const;

export type LengthChoiceId = (typeof LENGTH_CHOICES)[number]['id'];

/** "30 seconds", "2 min", "under 45s": the prompt already answers the length question. */
export const MENTIONS_LENGTH = /\d+\s*(s|sec|secs|seconds?|m|min|mins|minutes?)\b/i;
