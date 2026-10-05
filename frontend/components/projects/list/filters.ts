import type { ProjectView } from './projectState';

export type StatusFilter = 'all' | 'running' | 'ready' | 'failed';
export type SourceFilter = 'all' | 'youtube' | 'upload';
export type SortOrder = 'newest' | 'oldest' | 'name';
export type ViewMode = 'grid' | 'list';

/** Lives in the URL (`?q=&status=&source=&sort=&view=`) so Back and shared links keep it. */
export interface ProjectFilters {
  q: string;
  status: StatusFilter;
  source: SourceFilter;
  sort: SortOrder;
  view: ViewMode;
}

const pick = <T extends string>(value: string | null, allowed: readonly T[], fallback: T): T =>
  allowed.includes(value as T) ? (value as T) : fallback;

export function readFilters(params: URLSearchParams): ProjectFilters {
  return {
    q: params.get('q') ?? '',
    status: pick(params.get('status'), ['all', 'running', 'ready', 'failed'], 'all'),
    source: pick(params.get('source'), ['all', 'youtube', 'upload'], 'all'),
    sort: pick(params.get('sort'), ['newest', 'oldest', 'name'], 'newest'),
    view: pick(params.get('view'), ['grid', 'list'], 'grid'),
  };
}

const DEFAULTS: ProjectFilters = { q: '', status: 'all', source: 'all', sort: 'newest', view: 'grid' };

/** Only non-default values go in the URL. */
export function writeFilters(filters: ProjectFilters): string {
  const params = new URLSearchParams();
  for (const key of Object.keys(DEFAULTS) as (keyof ProjectFilters)[]) {
    const value = filters[key].trim();
    if (value && value !== DEFAULTS[key]) params.set(key, value);
  }
  const query = params.toString();
  return query ? `?${query}` : '';
}

export const hasNarrowing = (f: ProjectFilters) => f.q.trim() !== '' || f.status !== 'all' || f.source !== 'all';

export const clearedFilters = (f: ProjectFilters): ProjectFilters => ({ ...f, q: '', status: 'all', source: 'all' });

function matchesStatus(view: ProjectView, status: StatusFilter): boolean {
  if (status === 'all') return true;
  if (status === 'failed') return view.kind === 'failed' || view.kind === 'stopped';
  if (status === 'running') return view.kind === 'running' || view.kind === 'idle';
  return view.kind === 'ready';
}

function matchesSearchAndSource(view: ProjectView, f: ProjectFilters): boolean {
  const q = f.q.trim().toLowerCase();
  if (f.source !== 'all' && (view.project.source_type === 'upload') !== (f.source === 'upload')) return false;
  return !q || view.project.title.toLowerCase().includes(q);
}

const time = (view: ProjectView) => (view.project.created_at ? Date.parse(view.project.created_at) : 0);

const COMPARE: Record<SortOrder, (a: ProjectView, b: ProjectView) => number> = {
  newest: (a, b) => time(b) - time(a),
  oldest: (a, b) => time(a) - time(b),
  name: (a, b) => a.project.title.localeCompare(b.project.title, undefined, { sensitivity: 'base', numeric: true }),
};

export interface FilteredProjects {
  items: ProjectView[];
  /** Counts per status after search and source, for the status control. */
  counts: Record<StatusFilter, number>;
}

export function filterProjects(views: readonly ProjectView[], f: ProjectFilters): FilteredProjects {
  const searched = views.filter((view) => matchesSearchAndSource(view, f));
  const counts = {
    all: searched.length,
    running: searched.filter((v) => matchesStatus(v, 'running')).length,
    ready: searched.filter((v) => matchesStatus(v, 'ready')).length,
    failed: searched.filter((v) => matchesStatus(v, 'failed')).length,
  };
  return { items: searched.filter((view) => matchesStatus(view, f.status)).sort(COMPARE[f.sort]), counts };
}
