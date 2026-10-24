/**
 * Real Clipnera output shown on the landing page, unedited after export. Every
 * source is a Creative Commons Attribution (CC BY) upload by the person in it,
 * so each reel must keep its credit and link. Files live in /public/media/results.
 */
export interface LandingResult {
  id: string;
  title: string;
  creator: string;
  sourceUrl: string;
  video: string;
  poster: string;
  sourceLength: string;
  sourceKind: string;
  reelLength: string;
}

const AFIB: LandingResult = {
  id: 'afib',
  title: 'Can AFib cause a heart attack?',
  creator: 'Dr. AFib',
  sourceUrl: 'https://youtu.be/8-FEgCeTED0',
  video: '/media/results/afib.mp4',
  poster: '/media/results/afib.jpg',
  sourceLength: '3:08',
  sourceKind: 'explainer',
  reelLength: '0:40',
};

export const HERO_RESULT = {
  ...AFIB,
  before: { video: '/media/results/afib-before.mp4', poster: '/media/results/afib-before.jpg' },
};

export const RESULTS: LandingResult[] = [
  {
    id: 'sonia-shenoy',
    title: 'We need to normalize failure',
    creator: 'Sonia Shenoy Podcast',
    sourceUrl: 'https://youtu.be/euQNOOQnS-M',
    video: '/media/results/sonia-shenoy.mp4',
    poster: '/media/results/sonia-shenoy.jpg',
    sourceLength: '1:10:14',
    sourceKind: 'podcast',
    reelLength: '0:37',
  },
  {
    id: 'when-shift-happens',
    title: 'FOMO is the wrecker of wealth',
    creator: 'When Shift Happens',
    sourceUrl: 'https://youtu.be/tcWkTctWhAo',
    video: '/media/results/when-shift-happens.mp4',
    poster: '/media/results/when-shift-happens.jpg',
    sourceLength: '1:00:47',
    sourceKind: 'podcast',
    reelLength: '0:42',
  },
  AFIB,
  {
    id: 'ty-myers',
    title: 'What YouTube paid after 1,000 subscribers',
    creator: 'Ty Myers',
    sourceUrl: 'https://youtu.be/lVSHaGLY4tM',
    video: '/media/results/ty-myers.mp4',
    poster: '/media/results/ty-myers.jpg',
    sourceLength: '6:29',
    sourceKind: 'video',
    reelLength: '0:38',
  },
  {
    id: 'hellochen',
    title: 'What 75 Hard taught me',
    creator: 'HelloChen',
    sourceUrl: 'https://youtu.be/XEMiJSvOqrk',
    video: '/media/results/hellochen.mp4',
    poster: '/media/results/hellochen.jpg',
    sourceLength: '10:00',
    sourceKind: 'video',
    reelLength: '0:35',
  },
];

export const CAPTION_PREVIEW_FRAME = '/media/results/caption-preview.jpg';
