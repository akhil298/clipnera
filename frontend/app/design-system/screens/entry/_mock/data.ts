/**
 * Hard-coded sample data for the entry and dashboard mockups. Nothing here is
 * fetched; field names follow the Wave 3 contracts (openapi `Job`,
 * `InAppNotification`) where one exists, and the proposed folder API otherwise.
 */

export const ENTRY_BASE = '/design-system/screens/entry';

export const user = {
  name: 'Akhil Silveru',
  firstName: 'Akhil',
  email: 'akhil@example.com',
  initials: 'AS',
  plan: 'Pro',
  workspace: 'Akhil’s studio',
};

export const workspaces = [
  { id: 'ws1', name: 'Akhil’s studio', current: true },
  { id: 'ws2', name: 'Founder Podcast team', current: false },
];

export const credits = {
  balance: 1240,
  plan: 1040,
  planTotal: 1500,
  packs: 200,
  held: 18,
  renews: '12 Oct',
  minutes: 620,
};

export type ProjectState = 'ready' | 'processing' | 'uploading' | 'failed' | 'cancelled' | 'awaiting_credits';

export interface SampleProject {
  id: string;
  title: string;
  source: 'youtube' | 'upload';
  channel?: string;
  duration: string;
  updated: string;
  state: ProjectState;
  /** Live step in plain words, from `Job.progress.step_label`. */
  step?: string;
  percent?: number;
  clips: number;
  folderId?: string;
  reason?: string;
}

export const folders = [
  { id: 'f1', name: 'Founder Podcast · season 2', count: 6 },
  { id: 'f2', name: 'Client interviews', count: 3 },
  { id: 'f3', name: 'Tutorials', count: 4 },
];

export const projects: SampleProject[] = [
  {
    id: 'p1',
    title: 'Episode 41 — Why we stopped chasing views',
    source: 'youtube',
    channel: 'Founder Podcast',
    duration: '58:12',
    updated: '4 min ago',
    state: 'processing',
    step: 'Transcribing · 42 of 58 min',
    percent: 46,
    clips: 0,
    folderId: 'f1',
  },
  {
    id: 'p2',
    title: 'Masterclass: pricing your first product',
    source: 'upload',
    duration: '1:12:40',
    updated: '1 hour ago',
    state: 'uploading',
    step: 'Uploading · 62%',
    percent: 62,
    clips: 0,
    folderId: 'f3',
  },
  {
    id: 'p3',
    title: 'Episode 40 — The 3 a.m. routine',
    source: 'youtube',
    channel: 'Founder Podcast',
    duration: '47:05',
    updated: '3 hours ago',
    state: 'ready',
    clips: 9,
    folderId: 'f1',
  },
  {
    id: 'p4',
    title: 'Interview with Meera Rao, Rao Textiles',
    source: 'upload',
    duration: '32:18',
    updated: 'Yesterday',
    state: 'ready',
    clips: 6,
    folderId: 'f2',
  },
  {
    id: 'p5',
    title: 'Goa trip vlog, raw',
    source: 'upload',
    duration: '18:44',
    updated: '29 Sep',
    state: 'failed',
    clips: 0,
    reason: 'I couldn’t read the audio in goa-day2.mov. Nothing was charged.',
  },
  {
    id: 'p6',
    title: 'Episode 39 — One habit, double focus',
    source: 'youtube',
    channel: 'Founder Podcast',
    duration: '52:30',
    updated: '27 Sep',
    state: 'ready',
    clips: 11,
    folderId: 'f1',
  },
];

export const topClips = [
  { id: 'c1', title: 'The day I stopped chasing views', project: 'Episode 40', length: '0:41', score: 94 },
  { id: 'c2', title: 'Nobody tells you this part', project: 'Episode 40', length: '0:38', score: 88 },
  { id: 'c3', title: 'How Meera priced her first sari', project: 'Interview with Meera Rao', length: '0:52', score: 86 },
  { id: 'c4', title: 'One habit, double focus', project: 'Episode 39', length: '0:29', score: 83 },
  { id: 'c5', title: 'Stop optimising your morning', project: 'Episode 39', length: '0:33', score: 81 },
];

export const jobs = [
  { id: 'j1', project: 'Episode 41 — Why we stopped chasing views', label: 'Transcribing · 42 of 58 min', percent: 46 },
  { id: 'j2', project: 'Masterclass: pricing your first product', label: 'Uploading from this tab · 62%', percent: 62 },
];

export type NotificationKind = 'clips_ready' | 'failed' | 'scheduled' | 'credits' | 'reconnect';

export const notifications: Array<{
  id: string;
  kind: NotificationKind;
  title: string;
  message: string;
  time: string;
  read: boolean;
  group: 'Today' | 'Earlier';
}> = [
  {
    id: 'n1',
    kind: 'clips_ready',
    title: '9 clips ready',
    message: 'Episode 40 — The 3 a.m. routine',
    time: '3h',
    read: false,
    group: 'Today',
  },
  {
    id: 'n2',
    kind: 'credits',
    title: '200 credits added',
    message: 'Your credit pack payment was approved.',
    time: '5h',
    read: false,
    group: 'Today',
  },
  {
    id: 'n3',
    kind: 'scheduled',
    title: 'Posted to YouTube',
    message: '“One habit, double focus” went out at 7:00 pm.',
    time: '1d',
    read: true,
    group: 'Earlier',
  },
  {
    id: 'n4',
    kind: 'failed',
    title: 'Goa trip vlog, raw didn’t finish',
    message: 'I couldn’t read the audio. Nothing was charged.',
    time: '4d',
    read: true,
    group: 'Earlier',
  },
  {
    id: 'n5',
    kind: 'reconnect',
    title: 'Reconnect Instagram',
    message: '@foundercast disconnects in 2 days.',
    time: '5d',
    read: true,
    group: 'Earlier',
  },
];

/** Starter prompts per situation (01 §4 "Suggestions"). A click fills the bar; it never sends. */
export const suggestions = {
  noVideo: [
    'Find the 5 best moments',
    'Clips under 30 seconds',
    'Only the funny parts',
    'Hinglish captions',
    'Cut a trailer for this episode',
  ],
  withVideo: [
    'Find the 5 best moments',
    'Clips under 45 seconds with captions',
    'Pull every question the guest answers',
    'Keep the swearing out',
  ],
  clipsReady: ['Make 3 more from Episode 40', 'Shorter versions of my top clips', 'Same style as last week'],
};

/** The 11 pipeline steps folded into the five stages a person sees (doc §10). */
export const pipelineStages = [
  { id: 'import', label: 'Getting your video', detail: 'Downloading from YouTube or receiving your upload' },
  { id: 'audio', label: 'Cleaning up the audio', detail: 'Studio voice: echo, hiss and hum' },
  { id: 'transcribe', label: 'Transcribing', detail: 'Every word, with timings' },
  { id: 'moments', label: 'Finding the best moments', detail: 'Hooks, stories and takeaways, scored' },
  { id: 'clips', label: 'Making your clips', detail: 'Reframing to 9:16 and adding captions' },
] as const;
