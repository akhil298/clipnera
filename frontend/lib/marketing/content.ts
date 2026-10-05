/**
 * Landing copy (docs/revamp/screens/01-entry-and-dashboard.md §2). Facts are
 * carried over from the legacy landing and /editor pages; only YouTube and
 * Instagram are claimed for direct posting (D3).
 */

export const SECTION_LINKS = [
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Captions', href: '#captions' },
  { label: 'Editing', href: '#editing' },
  { label: 'Pricing', href: '#pricing' },
  { label: 'FAQ', href: '#faq' },
] as const;

export const SIGN_IN_HREF = '/login?next=/dashboard';

export const HERO_SUGGESTIONS = [
  'Find the 5 best moments',
  'Clips under 30 seconds',
  'Only the funny parts',
  'Hinglish captions',
  'Cut a trailer for this episode',
] as const;

/** Three clips from one podcast: the quote, where it sits in the 58:12 source, and its length in seconds. */
export const EXAMPLE_SOURCE = { title: 'Episode 41 · Why we stopped chasing views', seconds: 58 * 60 + 12 } as const;

export const EXAMPLE_CLIPS = [
  { quote: 'The day I stopped chasing views was the day the channel started growing.', format: 'Hot take', at: 4 * 60 + 12, length: 41, crop: 'object-left' },
  { quote: 'Nobody tells you the first hundred videos are practice. Mine were.', format: 'Story', at: 21 * 60 + 47, length: 38, crop: 'object-center' },
  { quote: 'Post the clip you’re slightly embarrassed by. That one travels.', format: 'Advice', at: 38 * 60 + 5, length: 29, crop: 'object-right' },
] as const;

export const FAQS = [
  {
    q: 'How does Clipnera choose the moments?',
    a: 'It transcribes your video word by word, then looks for strong hooks, emotional moments, useful takeaways and shareable lines, and scores each out of 100. Scores help you choose what to post first; they don’t predict views.',
  },
  {
    q: 'What can I upload?',
    a: 'A YouTube link, or a video file such as MP4, MOV, WebM or MKV. How long a video can be depends on your plan; the limits are listed under Pricing.',
  },
  {
    q: 'Can I edit the clips myself?',
    a: 'Yes. Trim, split, change captions and reframe by hand, or describe the change in a sentence. Your edits and Clipnera’s land on the same timeline, and every change can be undone.',
  },
  {
    q: 'Which languages work?',
    a: 'Prompts in English or Hinglish. Captions in English, Hindi, Telugu, Hinglish and Tenglish.',
  },
  {
    q: 'Can I change how captions look?',
    a: 'Yes. Pick a caption style, then adjust colours, uppercase and line count, and turn automatic emoji on or off. Creating and editing brand kits with your own colours and logo is part of Pro.',
  },
  {
    q: 'What does background noise reduction do?',
    a: 'It reduces steady noise such as fan or air-conditioner hum, electrical hum and room echo, and evens out voice tone. It works best on constant noise; it can’t fully remove loud or overlapping sounds.',
  },
  {
    q: 'Where can I publish?',
    a: 'Straight to YouTube Shorts and Instagram Reels, or download the MP4 for anywhere else. Titles and hashtags are suggested, and you edit them before posting. Scheduling is part of Pro.',
  },
  {
    q: 'Is the music and B-roll safe to post?',
    a: 'Yes. Both come from libraries licensed for commercial use, and each export lists any credit a track needs.',
  },
] as const;
