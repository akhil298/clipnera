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

interface SourceOverrides {
  title?: string;
  channelTitle?: string;
  thumbnailUrl?: string;
}

const YOUTUBE_HOSTS = new Set(['youtube.com', 'www.youtube.com', 'm.youtube.com']);
const YOUTUBE_ID_PATH_PREFIXES = new Set(['embed', 'shorts', 'live', 'v']);
const YOUTUBE_VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;

/**
 * Video id of a YouTube video link, or null for any other URL — YouTube is the
 * only supported source. Mirrors `extract_youtube_video_id` in backend/clip/youtube_url.py.
 */
export function extractYoutubeVideoId(input: string): string | null {
  const trimmed = input.trim();
  let url: URL;
  try {
    url = new URL(/^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`);
  } catch {
    return null;
  }

  const host = url.hostname.toLowerCase();
  const [first = '', second = ''] = url.pathname.split('/').filter(Boolean);
  let candidate = '';
  if (host === 'youtu.be') {
    candidate = first;
  } else if (YOUTUBE_HOSTS.has(host)) {
    candidate = first === 'watch' ? url.searchParams.get('v') ?? '' : YOUTUBE_ID_PATH_PREFIXES.has(first) ? second : '';
  }
  return YOUTUBE_VIDEO_ID.test(candidate) ? candidate : null;
}

/** Thumbnail for a YouTube URL (or bare video id), or '' when it is not one. */
export function youtubeThumbnailUrl(url: string): string {
  const videoId = extractYoutubeVideoId(url) ?? (YOUTUBE_VIDEO_ID.test(url) ? url : null);
  return videoId ? `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg` : '';
}

/**
 * Intelligent analyzer that inspects a YouTube / media URL or title
 * and returns clean, professional folder naming and metadata.
 */
export function analyzeVideoSource(inputUrlOrTitle: string, overrides?: SourceOverrides): ParsedUrlMeta {
  const meta = inferSourceMeta(inputUrlOrTitle, overrides);
  // The video's real thumbnail beats the stock placeholder picked by genre.
  const posterUrl = overrides?.thumbnailUrl || youtubeThumbnailUrl(inputUrlOrTitle.trim()) || meta.posterUrl;
  return { ...meta, posterUrl };
}

function inferSourceMeta(inputUrlOrTitle: string, overrides?: SourceOverrides): ParsedUrlMeta {
  const trimmed = inputUrlOrTitle.trim();
  const lower = trimmed.toLowerCase();

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

  let derivedName = trimmed;
  let channel = 'YouTube Ingest';

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
