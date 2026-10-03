/**
 * Hard-coded sample data for the mockups. Shapes follow the provisional
 * contracts in docs/revamp/05-broll.md §7 and 06-flags.md §8 by field name,
 * trimmed to what each screen shows. Nothing here is fetched.
 */

export type Orientation = 'portrait' | 'landscape' | 'square';

/** Stand-in "footage" colours for poster art. Content, not chrome, so not tokens. */
export type Look = readonly [sky: string, mid: string, ground: string];

export interface SampleShot {
  id: string;
  title: string;
  caption: string;
  duration: string;
  orientation: Orientation;
  look: Look;
  scope: 'platform' | 'mine';
  kind: 'stock' | 'upload' | 'generated';
  favourite?: boolean;
  locked?: boolean;
  match?: 'keyword' | 'meaning' | 'both';
  licence?: { name: string; author: string; attribution: string | null; required: boolean };
  status?: 'live' | 'retired' | 'held' | 'processing' | 'failed' | 'in_review' | 'blocked' | 'taken_down';
  sourceTitle?: string;
  at?: string;
}

const L = {
  city: ['#0b1d3a', '#f59e0b', '#111827'],
  dusk: ['#3b1d4a', '#fb923c', '#1f2937'],
  ocean: ['#0c4a6e', '#38bdf8', '#082f49'],
  forest: ['#14532d', '#86efac', '#052e16'],
  desk: ['#d6d3d1', '#78716c', '#44403c'],
  coffee: ['#451a03', '#d97706', '#1c1917'],
  snow: ['#e0f2fe', '#f8fafc', '#94a3b8'],
  market: ['#7c2d12', '#facc15', '#292524'],
  night: ['#020617', '#64748b', '#0f172a'],
  field: ['#fde68a', '#a3e635', '#3f6212'],
  studio: ['#262626', '#e5e5e5', '#0a0a0a'],
  rain: ['#1e293b', '#94a3b8', '#0f172a'],
} as const satisfies Record<string, Look>;

const pexels = (author: string) => ({ name: 'Pexels License', author, attribution: `Video by ${author} on Pexels`, required: false });
const ccBy = (author: string) => ({ name: 'CC BY 4.0', author, attribution: `"Monsoon street" by ${author}, CC BY 4.0`, required: true });

export const PLATFORM_SHOTS: SampleShot[] = [
  { id: 'p1', title: 'Drone over city lights at night', caption: 'Slow aerial push over a lit city grid at night', duration: '0:12', orientation: 'portrait', look: L.city, scope: 'platform', kind: 'stock', match: 'both', licence: pexels('Ravi Kumar') },
  { id: 'p2', title: 'Pouring coffee into a white mug', caption: 'Close-up of coffee poured into a white mug on a wooden table', duration: '0:06', orientation: 'portrait', look: L.coffee, scope: 'platform', kind: 'stock', favourite: true, match: 'keyword', licence: pexels('Anna Shvets') },
  { id: 'p3', title: 'Waves at golden hour', caption: 'Waves rolling onto a beach at sunset', duration: '0:09', orientation: 'landscape', look: L.dusk, scope: 'platform', kind: 'stock', match: 'meaning', licence: pexels('Kelly L') },
  { id: 'p4', title: 'Typing on a laptop, top view', caption: 'Hands typing on a laptop seen from above', duration: '0:08', orientation: 'portrait', look: L.desk, scope: 'platform', kind: 'stock', licence: pexels('Mikhail Nilov') },
  { id: 'p5', title: 'Monsoon street, Mumbai', caption: 'Rain on a busy street with yellow taxis', duration: '0:14', orientation: 'portrait', look: L.rain, scope: 'platform', kind: 'stock', match: 'meaning', licence: ccBy('S. Rao') },
  { id: 'p6', title: 'Spice market stalls', caption: 'Colourful spice stalls in an Indian market', duration: '0:07', orientation: 'square', look: L.market, scope: 'platform', kind: 'stock', licence: pexels('Yogendra Singh') },
  { id: 'p7', title: 'Forest canopy walk', caption: 'Camera moves under a dense green canopy', duration: '0:11', orientation: 'portrait', look: L.forest, scope: 'platform', kind: 'stock', licence: pexels('Lukas Rychvalsky') },
  { id: 'p8', title: 'Snowy ridge time-lapse', caption: 'Clouds racing over a snowy mountain ridge', duration: '0:10', orientation: 'landscape', look: L.snow, scope: 'platform', kind: 'stock', licence: { name: 'Public domain (US government)', author: 'NASA', attribution: 'Courtesy NASA', required: false } },
  { id: 'p9', title: 'Stock chart on a monitor', caption: 'Green and red candles on a trading screen', duration: '0:05', orientation: 'portrait', look: L.night, scope: 'platform', kind: 'stock', licence: pexels('Tima Miroshnichenko') },
  { id: 'p10', title: 'Mustard field in wind', caption: 'Yellow mustard flowers moving in the wind', duration: '0:13', orientation: 'portrait', look: L.field, scope: 'platform', kind: 'stock', licence: pexels('Harsh Patel') },
  { id: 'p11', title: 'Ocean from above', caption: 'Top-down view of blue water and surf', duration: '0:09', orientation: 'square', look: L.ocean, scope: 'platform', kind: 'stock', licence: pexels('Ben Mack') },
  { id: 'p12', title: 'Studio light flicker', caption: 'A softbox switching on in a dark studio', duration: '0:04', orientation: 'portrait', look: L.studio, scope: 'platform', kind: 'stock', licence: pexels('Ron Lach') },
];

export const MY_SOURCES: (SampleShot & { shots: number; size: string; usedIn: number; state: 'ready' | 'processing' | 'held' | 'failed'; step?: string })[] = [
  { id: 'm1', title: 'Beach run', caption: 'Running along the shore at sunrise', duration: '2:41', orientation: 'portrait', look: L.ocean, scope: 'mine', kind: 'upload', shots: 6, size: '412 MB', usedIn: 2, state: 'ready' },
  { id: 'm2', title: 'Product shots — bottle', caption: 'Water bottle on a turntable', duration: '1:05', orientation: 'square', look: L.studio, scope: 'mine', kind: 'upload', shots: 4, size: '188 MB', usedIn: 0, state: 'ready' },
  { id: 'm3', title: 'Office b-roll', caption: 'Team at desks, wide shots', duration: '4:12', orientation: 'landscape', look: L.desk, scope: 'mine', kind: 'upload', shots: 0, size: '1.1 GB', usedIn: 0, state: 'processing', step: 'Finding shots' },
  { id: 'm4', title: 'Cafe interior', caption: 'Coffee bar and customers', duration: '0:48', orientation: 'portrait', look: L.coffee, scope: 'mine', kind: 'upload', shots: 3, size: '96 MB', usedIn: 1, state: 'ready', favourite: true },
  { id: 'm5', title: 'Night drive', caption: 'Dashboard view of a highway at night', duration: '1:30', orientation: 'landscape', look: L.night, scope: 'mine', kind: 'upload', shots: 0, size: '240 MB', usedIn: 0, state: 'held' },
  { id: 'm6', title: 'AI shot: chai being poured', caption: 'Generated: chai poured into a glass', duration: '0:08', orientation: 'portrait', look: L.market, scope: 'mine', kind: 'generated', shots: 1, size: '14 MB', usedIn: 1, state: 'ready' },
];

export const BEACH_MOMENTS: SampleShot[] = [
  { id: 'b1', title: 'Feet in the surf', caption: 'Close-up of feet splashing in shallow water', duration: '0:06', orientation: 'portrait', look: L.ocean, scope: 'mine', kind: 'upload', sourceTitle: 'Beach run', at: '0:00' },
  { id: 'b2', title: 'Wide run along the shore', caption: 'Runner small in frame, long beach', duration: '0:09', orientation: 'portrait', look: L.dusk, scope: 'mine', kind: 'upload', sourceTitle: 'Beach run', at: '0:06' },
  { id: 'b3', title: 'Sun flare through hair', caption: 'Back-lit close-up with sun flare', duration: '0:05', orientation: 'portrait', look: L.field, scope: 'mine', kind: 'upload', sourceTitle: 'Beach run', at: '0:42' },
  { id: 'b4', title: 'Stopping, catching breath', caption: 'Runner stops and looks at the sea', duration: '0:08', orientation: 'portrait', look: L.ocean, scope: 'mine', kind: 'upload', sourceTitle: 'Beach run', at: '1:10' },
];

export const COLLECTIONS = [
  { id: 'c1', name: 'Product shots', count: 14, curated: false, cover: L.studio },
  { id: 'c2', name: 'Morning routine series', count: 9, curated: false, cover: L.coffee },
  { id: 'c3', name: 'City at night', count: 32, curated: true, cover: L.city },
  { id: 'c4', name: 'Business & finance', count: 48, curated: true, cover: L.night },
  { id: 'c5', name: 'India', count: 61, curated: true, cover: L.market },
] as const;

export const CATEGORIES = ['Cities', 'Nature', 'People', 'Work & tech', 'Food & drink', 'Travel', 'Sport', 'Abstract'] as const;

export const TRASH = [
  { id: 't1', title: 'Old intro take', size: '320 MB', daysLeft: 27, usedIn: 0, look: L.studio },
  { id: 't2', title: 'Rooftop timelapse', size: '1.4 GB', daysLeft: 12, usedIn: 1, look: L.city },
  { id: 't3', title: 'Blurry handheld', size: '58 MB', daysLeft: 2, usedIn: 0, look: L.rain },
] as const;
