import { CaptionConfig } from '@/lib/types';

export interface EmojiCollection {
  id: string;
  name: string;
  description: string;
  emoji: string;
  emojis: string[];
}

export const EMOJI_COLLECTIONS: EmojiCollection[] = [
  {
    id: 'skull_fire',
    name: 'Skull & Fire',
    description: '💀🔥 — The ultimate viral combo',
    emoji: '💀🔥',
    emojis: ['💀', '🔥'],
  },
  {
    id: 'fire_skull',
    name: 'Fire & Skull',
    description: '🔥💀 — Fire first, then skull',
    emoji: '🔥💀',
    emojis: ['🔥', '💀'],
  },
  {
    id: 'explosion',
    name: 'Explosion',
    description: '💥💀🔥 — Maximum impact',
    emoji: '💥💀🔥',
    emojis: ['💥', '💀', '🔥'],
  },
  {
    id: 'arrow',
    name: 'Arrow Point',
    description: '👉🛡️ — Direct and pointing',
    emoji: '👉🛡️',
    emojis: ['👉', '🛡️'],
  },
  {
    id: 'money_eyes',
    name: 'Money Eyes',
    description: '💰👀 — Rich and watching',
    emoji: '💰👀',
    emojis: ['💰', '👀'],
  },
  {
    id: 'rocket',
    name: 'Rocket',
    description: '🚀👉 — Blast off energy',
    emoji: '🚀👉',
    emojis: ['🚀', '👉'],
  },
  {
    id: 'thumbs_up',
    name: 'Thumbs Up',
    description: '👍👉 — Positive push',
    emoji: '👍👉',
    emojis: ['👍', '👉'],
  },
  {
    id: 'crown',
    name: 'Crown',
    description: '👑👉 — Royal statement',
    emoji: '👑👉',
    emojis: ['👑', '👉'],
  },
  {
    id: 'lightning',
    name: 'Lightning',
    description: '⚡💡 — Shock and bright ideas',
    emoji: '⚡💡',
    emojis: ['⚡', '💡'],
  },
  {
    id: 'sparkles',
    name: 'Sparkles',
    description: '✨✨ — Magical emphasis',
    emoji: '✨✨',
    emojis: ['✨', '✨'],
  },
  {
    id: 'shock',
    name: 'Shock',
    description: '😡😡⚡ — Intense reaction',
    emoji: '😡😡⚡',
    emojis: ['😡', '😡', '⚡'],
  },
  {
    id: 'crown_skull',
    name: 'Crown Skull Fire',
    description: '👑💀🔥 — Death to crowns',
    emoji: '👑💀🔥',
    emojis: ['👑', '💀', '🔥'],
  },
  {
    id: 'skull_crossbones',
    name: 'Skull & Crossbones',
    description: '💀☠️ — Danger zone',
    emoji: '💀☠️',
    emojis: ['💀', '☠️'],
  },
  {
    id: 'ghost',
    name: 'Ghost',
    description: '👻💀 — Spooky impact',
    emoji: '👻💀',
    emojis: ['👻', '💀'],
  },
  {
    id: 'dice',
    name: 'Dice',
    description: '🎲💀 — Chance and fear',
    emoji: '🎲💀',
    emojis: ['🎲', '💀'],
  },
  {
    id: 'fist',
    name: 'Fist',
    description: '👊👉 — Punch and point',
    emoji: '👊👉',
    emojis: ['👊', '👉'],
  },
  {
    id: 'eye_fire',
    name: 'Eye Fire',
    description: '👀🔥 — Burning attention',
    emoji: '👀🔥',
    emojis: ['👀', '🔥'],
  },
  {
    id: 'clown',
    name: 'Clown',
    description: '🤡🔥 — Clown fire',
    emoji: '🤡🔥',
    emojis: ['🤡', '🔥'],
  },
];

export const getEmojiCollection = (id: string): EmojiCollection => {
  return EMOJI_COLLECTIONS.find((c) => c.id === id) || EMOJI_COLLECTIONS[0];
};

export const getAllEmojiCollectionIds = (): string[] => {
  return EMOJI_COLLECTIONS.map((c) => c.id);
};
