import { ViralClip } from '@/lib/types';

export interface ParsedUrlMeta {
  cleanTitle: string;
  folderName: string;
  sourceChannel: string;
  sourceUrl: string;
  genre: string;
  folderCategory: 'YouTube Ingest' | 'Podcast' | 'Keynote' | 'Webinar' | 'Interview' | 'Masterclass' | 'Upload' | 'Custom';
  folderColor: 'amber' | 'sky' | 'emerald' | 'rose' | 'purple' | 'indigo';
  tags: string[];
  duration: number;
  posterUrl: string;
}

/**
 * Intelligent analyzer that inspects a YouTube / media URL or title
 * and returns clean, professional folder naming and metadata.
 */
export function analyzeVideoSource(inputUrlOrTitle: string, overrides?: { title?: string; channelTitle?: string }): ParsedUrlMeta {
  const trimmed = inputUrlOrTitle.trim();
  const lower = trimmed.toLowerCase();

  // Preset topic detections
  if (lower.includes('hormozi') || lower.includes('100m') || lower.includes('leads') || lower.includes('offers')) {
    return {
      cleanTitle: overrides?.title || 'Alex Hormozi: $100M Value Equation & Acquisition Strategy',
      folderName: overrides?.title ? `${overrides.title} (Clips Folder)` : 'Alex Hormozi — $100M Leads Masterclass',
      sourceChannel: overrides?.channelTitle || 'Alex Hormozi',
      sourceUrl: trimmed.startsWith('http') ? trimmed : 'https://www.youtube.com/watch?v=100m-leads-masterclass',
      genre: 'Business & Entrepreneurship',
      folderCategory: 'YouTube Ingest',
      folderColor: 'amber',
      tags: ['Sales', 'Scaling', 'Customer Acquisition', 'Offers'],
      duration: 620,
      posterUrl: 'https://images.unsplash.com/photo-1557804506-669a67965ba0?w=800&auto=format&fit=crop&q=80',
    };
  }

  if (lower.includes('huberman') || lower.includes('dopamine') || lower.includes('focus') || lower.includes('sleep')) {
    return {
      cleanTitle: overrides?.title || 'Dr. Andrew Huberman: Master Dopamine, Drive & Daily Focus',
      folderName: overrides?.title ? `${overrides.title} (Clips Folder)` : 'Huberman Lab — Dopamine & Focus Protocols',
      sourceChannel: overrides?.channelTitle || 'Huberman Lab',
      sourceUrl: trimmed.startsWith('http') ? trimmed : 'https://www.youtube.com/watch?v=dopamine-focus-protocols',
      genre: 'Neuroscience & Peak Performance',
      folderCategory: 'Podcast',
      folderColor: 'sky',
      tags: ['Neuroscience', 'Focus', 'Dopamine', 'Habits'],
      duration: 780,
      posterUrl: 'https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=800&auto=format&fit=crop&q=80',
    };
  }

  if (lower.includes('naval') || lower.includes('wealth') || lower.includes('rich') || lower.includes('ravikant')) {
    return {
      cleanTitle: overrides?.title || 'Naval Ravikant: How to Get Rich Without Getting Lucky',
      folderName: overrides?.title ? `${overrides.title} (Clips Folder)` : 'Naval Ravikant — Wealth Creation Principles',
      sourceChannel: overrides?.channelTitle || 'Naval',
      sourceUrl: trimmed.startsWith('http') ? trimmed : 'https://www.youtube.com/watch?v=how-to-get-rich',
      genre: 'Philosophy & Wealth Creation',
      folderCategory: 'Podcast',
      folderColor: 'emerald',
      tags: ['Leverage', 'Judgment', 'Equity', 'Specific Knowledge'],
      duration: 540,
      posterUrl: 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&auto=format&fit=crop&q=80',
    };
  }

  if (lower.includes('altman') || lower.includes('sam') || lower.includes('openai') || lower.includes('gpt') || lower.includes('ai')) {
    return {
      cleanTitle: overrides?.title || 'Sam Altman & Dario Amodei: The Future of Autonomous AI & Compute',
      folderName: overrides?.title ? `${overrides.title} (Clips Folder)` : 'OpenAI / Tech — Future of Autonomous AI',
      sourceChannel: overrides?.channelTitle || 'Y Combinator & AI Summit',
      sourceUrl: trimmed.startsWith('http') ? trimmed : 'https://www.youtube.com/watch?v=future-of-ai-compute',
      genre: 'Artificial Intelligence & Startups',
      folderCategory: 'Keynote',
      folderColor: 'purple',
      tags: ['AI Agents', 'Silicon Valley', 'Compute', 'Startups'],
      duration: 690,
      posterUrl: 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800&auto=format&fit=crop&q=80',
    };
  }

  if (lower.includes('all-in') || lower.includes('chamath') || lower.includes('sacks') || lower.includes('bestie')) {
    return {
      cleanTitle: overrides?.title || 'All-In Podcast: Macroeconomics, Tech VC & Venture Outlook',
      folderName: overrides?.title ? `${overrides.title} (Clips Folder)` : 'All-In Podcast — Macro & Tech VC Deep-Dive',
      sourceChannel: overrides?.channelTitle || 'All-In Podcast',
      sourceUrl: trimmed.startsWith('http') ? trimmed : 'https://www.youtube.com/watch?v=all-in-podcast-macro',
      genre: 'Venture Capital & Politics',
      folderCategory: 'Podcast',
      folderColor: 'rose',
      tags: ['Macro', 'Venture Capital', 'Tech', 'Economy'],
      duration: 850,
      posterUrl: 'https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=800&auto=format&fit=crop&q=80',
    };
  }

  // Default clean extraction
  let derivedName = trimmed;
  let channel = 'YouTube Ingest';

  // If it's a raw URL, try to extract a clean slug or fallback title
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    try {
      const urlObj = new URL(trimmed);
      const videoId = urlObj.searchParams.get('v') || urlObj.pathname.split('/').filter(Boolean).pop() || 'Video';
      derivedName = `YouTube Video [${videoId.slice(0, 10)}]`;
      channel = urlObj.hostname.replace('www.', '');
    } catch {
      derivedName = 'YouTube Viral Ingestion Project';
    }
  }

  if (!derivedName || derivedName.length < 3) {
    derivedName = 'Viral Repurposing Project';
  }

  return {
    cleanTitle: overrides?.title || derivedName,
    folderName: overrides?.title ? `${overrides.title} (Clips Folder)` : `${derivedName} (Clips Folder)`,
    sourceChannel: overrides?.channelTitle || channel,
    sourceUrl: trimmed.startsWith('http') ? trimmed : `https://youtube.com/watch?v=sample`,
    genre: 'Creator & Podcast Repurposing',
    folderCategory: 'YouTube Ingest',
    folderColor: 'amber',
    tags: ['Viral Hooks', 'Social Growth', 'Subtitles', 'Auto-Zoom'],
    duration: 480,
    posterUrl: 'https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=800&auto=format&fit=crop&q=80',
  };
}

/**
 * Creates rich, high-retention viral clips for a newly created folder project
 */
export function generateClipsForProject(meta: ParsedUrlMeta, projectId: string): ViralClip[] {
  const { folderName, cleanTitle, tags } = meta;

  const clip1: ViralClip = {
    id: `${projectId}-clip-1`,
    title: `The 3-Second Retention Rule (${tags[0] || 'Core Hook'})`,
    hook: `Most people get this completely backward in their first 3 seconds...`,
    viralityScore: 98,
    hookScore: 99,
    engagementScore: 97,
    startTime: 14,
    endTime: 48,
    duration: 34,
    rationale: 'Massive opening curiosity gap combined with immediate contrarian statement; estimated +43% watch-through.',
    suggestedAspectRatio: '9:16',
    suggestedLayout: 'single_speaker',
    aspectRatio: '9:16',
    layoutMode: 'single_speaker',
    keywords: [tags[0] || 'Viral', 'Strategy', 'Attention', 'Retention'],
    emojiHighlights: ['🔥', '⚡', '🤯'],
    autoBrollKeywords: ['audience', 'growth', 'metrics'],
    transcriptSegments: [
      {
        id: 'ts-1',
        speaker: 'Main Speaker',
        speakerColor: '#f59e0b',
        start: 14,
        end: 28,
        text: 'If you want to explode on short-form platforms, stop introducing yourself.',
        words: [
          { id: 'w1', text: 'If', start: 14, end: 14.3 },
          { id: 'w2', text: 'you', start: 14.3, end: 14.6 },
          { id: 'w3', text: 'want', start: 14.6, end: 14.9 },
          { id: 'w4', text: 'to', start: 14.9, end: 15.1 },
          { id: 'w5', text: 'EXPLODE', start: 15.1, end: 15.6, highlighted: true, emoji: '🔥' },
          { id: 'w6', text: 'on', start: 15.6, end: 15.8 },
          { id: 'w7', text: 'short-form,', start: 15.8, end: 16.4, highlighted: true },
          { id: 'w8', text: 'stop', start: 16.4, end: 16.8, highlighted: true, emoji: '🛑' },
          { id: 'w9', text: 'introducing', start: 16.8, end: 17.5 },
          { id: 'w10', text: 'yourself.', start: 17.5, end: 18.0 },
        ],
      },
      {
        id: 'ts-2',
        speaker: 'Main Speaker',
        speakerColor: '#f59e0b',
        start: 28,
        end: 48,
        text: 'Deliver the climax payoff in the first five seconds and hold the cliffhanger until the loop.',
        words: [
          { id: 'w11', text: 'Deliver', start: 28, end: 28.5 },
          { id: 'w12', text: 'the', start: 28.5, end: 28.7 },
          { id: 'w13', text: 'PAYOFF', start: 28.7, end: 29.3, highlighted: true, emoji: '💡' },
          { id: 'w14', text: 'immediately.', start: 29.3, end: 30.0 },
        ],
      },
    ],
    bRollOverlays: [
      {
        id: 'br-1',
        start: 2,
        duration: 3.5,
        title: 'Virality Curve Growth',
        imageUrl: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=400&auto=format&fit=crop&q=80',
        category: 'growth',
        opacity: 0.9,
        transition: 'zoom',
      },
    ],
    soundEffects: [
      { id: 'sfx-1', time: 1.1, name: 'Cinematic Whoosh', type: 'whoosh', volume: 0.8 },
      { id: 'sfx-2', time: 3.4, name: 'Pop Accent', type: 'pop', volume: 0.7 },
    ],
    captionConfig: {
      preset: 'hormozi',
      fontSize: 22,
      fontFamily: 'Syne',
      textColor: '#FFFFFF',
      highlightColor: '#FACC15',
      secondaryHighlightColor: '#4ADE80',
      hasBgBox: false,
      bgBoxColor: 'rgba(0,0,0,0.85)',
      uppercase: true,
      animation: 'bounce',
      positionY: 72,
      emojisEnabled: true,
      maxWordsPerLine: 3,
      shadowIntensity: 0.8,
    },
    autoZoom: {
      enabled: true,
      frequency: 'medium',
      scale: 1.12,
    },
    autoReframe: {
      mode: 'speaker_tracking',
      speakerCropX: 0.5,
      speakerSmoothing: 0.85,
    },
    socialOptimization: {
      hashtags: ['#ViralHacks', '#CreatorEconomy', '#ShortsGrowth', '#VideoEditing'],
      optimizedHooks: [
        { type: 'Curiosity Gap', text: 'The 1 mistake cost creators 90% of views...', strength: 99, predictedRetention: '84%' },
        { type: 'Bold Statement', text: 'Stop doing this in your videos immediately.', strength: 96, predictedRetention: '81%' },
      ],
      targetPlatforms: ['tiktok', 'instagram', 'youtube', 'x'],
      postStatus: 'draft',
    },
  };

  const clip2: ViralClip = {
    id: `${projectId}-clip-2`,
    title: `The Leverage Secret (${tags[1] || 'Framework'})`,
    hook: `If you understand this one psychological loop, you can scale indefinitely...`,
    viralityScore: 94,
    hookScore: 95,
    engagementScore: 93,
    startTime: 72,
    endTime: 114,
    duration: 42,
    rationale: 'High conceptual insight with clear actionable step-by-step breakdown.',
    suggestedAspectRatio: '9:16',
    suggestedLayout: 'single_speaker',
    aspectRatio: '9:16',
    layoutMode: 'single_speaker',
    keywords: [tags[1] || 'Leverage', 'Framework', 'Scale'],
    emojiHighlights: ['🚀', '📈'],
    autoBrollKeywords: ['technology', 'scale'],
    transcriptSegments: [
      {
        id: 'ts-3',
        speaker: 'Main Speaker',
        speakerColor: '#f59e0b',
        start: 72,
        end: 95,
        text: 'Code and media are permissionless leverage. You do the work once and it works for you forever.',
        words: [
          { id: 'w21', text: 'Code', start: 72, end: 72.5, highlighted: true, emoji: '💻' },
          { id: 'w22', text: 'and', start: 72.5, end: 72.7 },
          { id: 'w23', text: 'media', start: 72.7, end: 73.2, highlighted: true, emoji: '🎥' },
          { id: 'w24', text: 'are', start: 73.2, end: 73.4 },
          { id: 'w25', text: 'LEVERAGE.', start: 73.4, end: 74.0, highlighted: true, emoji: '🚀' },
        ],
      },
    ],
    bRollOverlays: [],
    soundEffects: [
      { id: 'sfx-3', time: 0.8, name: 'Sub Drop Climax', type: 'sub_drop', volume: 0.85 },
    ],
    captionConfig: {
      preset: 'mrbeast',
      fontSize: 24,
      fontFamily: 'Plus Jakarta Sans',
      textColor: '#FFFFFF',
      highlightColor: '#38BDF8',
      secondaryHighlightColor: '#F43F5E',
      hasBgBox: true,
      bgBoxColor: 'rgba(0,0,0,0.85)',
      uppercase: true,
      animation: 'pop',
      positionY: 70,
      emojisEnabled: true,
      maxWordsPerLine: 2,
      shadowIntensity: 0.9,
    },
    autoZoom: {
      enabled: true,
      frequency: 'high',
      scale: 1.15,
    },
    autoReframe: {
      mode: 'speaker_tracking',
      speakerCropX: 0.5,
      speakerSmoothing: 0.9,
    },
    socialOptimization: {
      hashtags: ['#Productivity', '#Mindset', '#Growth', '#Scale'],
      optimizedHooks: [
        { type: 'Counter-Intuitive', text: 'Working harder is the slowest way to win.', strength: 95, predictedRetention: '80%' },
      ],
      targetPlatforms: ['tiktok', 'instagram', 'youtube'],
      postStatus: 'draft',
    },
  };

  const clip3: ViralClip = {
    id: `${projectId}-clip-3`,
    title: `The Unfair Advantage Breakdown`,
    hook: `Why the top 1% achieve 100x results while everyone else burns out...`,
    viralityScore: 91,
    hookScore: 92,
    engagementScore: 90,
    startTime: 140,
    endTime: 178,
    duration: 38,
    rationale: 'Strong identity resonance & high shareability across professional and creator networks.',
    suggestedAspectRatio: '9:16',
    suggestedLayout: 'single_speaker',
    aspectRatio: '9:16',
    layoutMode: 'single_speaker',
    keywords: ['Advantage', 'Discipline', 'Focus'],
    emojiHighlights: ['🎯', '✨'],
    autoBrollKeywords: ['focus', 'strategy'],
    transcriptSegments: [],
    bRollOverlays: [],
    soundEffects: [],
    captionConfig: {
      preset: 'cyberpunk',
      fontSize: 22,
      fontFamily: 'Syne',
      textColor: '#F0ABFC',
      highlightColor: '#22D3EE',
      secondaryHighlightColor: '#E879F9',
      hasBgBox: false,
      bgBoxColor: 'rgba(0,0,0,0.85)',
      uppercase: true,
      animation: 'glow',
      positionY: 72,
      emojisEnabled: true,
      maxWordsPerLine: 3,
      shadowIntensity: 0.9,
    },
    autoZoom: {
      enabled: true,
      frequency: 'subtle',
      scale: 1.08,
    },
    autoReframe: {
      mode: 'speaker_tracking',
      speakerCropX: 0.5,
      speakerSmoothing: 0.8,
    },
    socialOptimization: {
      hashtags: ['#DeepWork', '#Focus', '#Discipline', '#Success'],
      optimizedHooks: [
        { type: 'Question Hook', text: 'Do you have this specific unfair advantage?', strength: 91, predictedRetention: '77%' },
      ],
      targetPlatforms: ['tiktok', 'instagram', 'youtube', 'x'],
      postStatus: 'draft',
    },
  };

  return [clip1, clip2, clip3];
}
