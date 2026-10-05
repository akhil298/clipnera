/**
 * Every entry screen and its states, shared by the index page and each
 * screen's `?state=` switcher. Server-safe (no client code).
 */

export interface StateOption {
  value: string;
  label: string;
}

export interface ScreenSpec {
  slug: string;
  title: string;
  url: string;
  flag: string;
  summary: string;
  states: ReadonlyArray<StateOption>;
}

export const SCREENS = {
  landing: {
    slug: 'landing',
    title: 'Landing',
    url: '/ (and /editor → /#editing)',
    flag: 'new_ui_auth',
    summary: 'One prompt-first marketing page. The hero takes a prompt plus a link or file and carries them through sign-in.',
    states: [
      { value: 'default', label: 'Signed out' },
      { value: 'typed', label: 'Link + prompt typed' },
      { value: 'sign-in', label: 'Send → sign-in dialog' },
      { value: 'signed-in', label: 'Signed in' },
      { value: 'bad-link', label: 'Link not supported' },
      { value: 'pricing-error', label: 'Pricing failed' },
      { value: 'menu', label: 'Phone menu' },
    ],
  },
  'sign-in': {
    slug: 'sign-in',
    title: 'Sign in',
    url: '/login, /signup, /login/google',
    flag: 'new_ui_auth',
    summary: 'One sign-in surface, as a page and as a dialog. Consent once, for new accounts only. Prompt, link and file kept.',
    states: [
      { value: 'default', label: 'First time on this device' },
      { value: 'carried', label: 'Carrying a prompt' },
      { value: 'returning', label: 'Returning device' },
      { value: 'expired', label: 'Session ended' },
      { value: 'redirecting', label: 'Going to Google' },
      { value: 'callback', label: 'Signing in (callback)' },
      { value: 'consent', label: 'New account, consent needed' },
      { value: 'cancelled', label: 'Cancelled at Google' },
      { value: 'stale', label: 'Link too old' },
      { value: 'offline', label: 'Offline' },
    ],
  },
  onboarding: {
    slug: 'onboarding',
    title: 'Onboarding (first run)',
    url: '/dashboard (first visit) — sheet over Home',
    flag: 'new_ui_dashboard',
    summary: 'Two skippable questions on the first visit, then Home tuned to the answers. Skipped entirely when a prompt was carried in.',
    states: [
      { value: 'step-1', label: 'What you make' },
      { value: 'step-2', label: 'Where you post' },
      { value: 'saving', label: 'Saving' },
      { value: 'carried', label: 'Arrived with a prompt' },
      { value: 'error', label: 'Couldn’t save' },
    ],
  },
  shell: {
    slug: 'shell',
    title: 'App shell',
    url: 'Every /dashboard page',
    flag: 'new_ui_shell',
    summary: 'Sidebar, header, phone tab bar, notifications drawer, credits popover, activity indicator and the ⌘K prompt entry.',
    states: [
      { value: 'default', label: 'Default' },
      { value: 'notifications', label: 'Notifications' },
      { value: 'notifications-empty', label: 'Notifications empty' },
      { value: 'credits', label: 'Credits' },
      { value: 'credits-pending', label: 'Payment being checked' },
      { value: 'activity', label: 'Activity' },
      { value: 'command', label: '⌘K prompt entry' },
      { value: 'command-go', label: '/go navigation' },
      { value: 'rail', label: 'Collapsed rail' },
      { value: 'more', label: 'Phone: More' },
      { value: 'offline', label: 'Offline' },
    ],
  },
  home: {
    slug: 'home',
    title: 'Home',
    url: '/dashboard',
    flag: 'new_ui_dashboard',
    summary: 'Prompt-first hero (prompt + link or file), starter chips, work in progress, recent projects and top clips.',
    states: [
      { value: 'default', label: 'Returning' },
      { value: 'first-run', label: 'First run' },
      { value: 'restored', label: 'Prompt carried from landing' },
      { value: 'attached', label: 'Video attached' },
      { value: 'loading', label: 'Loading' },
      { value: 'partial', label: 'Part failed' },
      { value: 'out-of-credits', label: 'Out of credits' },
      { value: 'offline', label: 'Offline' },
    ],
  },
  projects: {
    slug: 'projects',
    title: 'Projects and folders',
    url: '/dashboard/projects (?folder=, /dashboard/folders → 308)',
    flag: 'new_ui_dashboard',
    summary: 'Every project with live status, real server-side folders, search, filters, grid or list, move, rename and retry.',
    states: [
      { value: 'default', label: 'All projects' },
      { value: 'folder', label: 'Inside a folder' },
      { value: 'list', label: 'List view' },
      { value: 'selecting', label: 'Selecting' },
      { value: 'move', label: 'Move to folder' },
      { value: 'new-folder', label: 'New folder' },
      { value: 'delete', label: 'Delete project' },
      { value: 'loading', label: 'Loading' },
      { value: 'empty', label: 'No projects' },
      { value: 'no-results', label: 'No matches' },
      { value: 'error', label: 'Couldn’t load' },
    ],
  },
  upload: {
    slug: 'upload',
    title: 'New video (upload)',
    url: '/dashboard/upload (modal over the current page)',
    flag: 'new_ui_dashboard',
    summary: 'Confirm source, prompt, folder and cost; options folded away. The server starts the work, so the tab can close.',
    states: [
      { value: 'link', label: 'YouTube link' },
      { value: 'checking', label: 'Checking link' },
      { value: 'file', label: 'File picked' },
      { value: 'drop', label: 'Drop a file' },
      { value: 'options', label: 'Options open' },
      { value: 'too-long', label: 'Too long for plan' },
      { value: 'no-credits', label: 'Not enough credits' },
      { value: 'starting', label: 'Starting' },
      { value: 'error', label: 'Couldn’t start' },
    ],
  },
  progress: {
    slug: 'progress',
    title: 'Project progress',
    url: '/dashboard/projects/[projectId] (while processing)',
    flag: 'new_ui_dashboard',
    summary: 'The live step list for one project. Opens from every card, toast and the activity indicator.',
    states: [
      { value: 'uploading', label: 'Uploading' },
      { value: 'running', label: 'Running' },
      { value: 'expanded', label: 'Steps expanded' },
      { value: 'waiting-credits', label: 'Waiting for credits' },
      { value: 'reconnecting', label: 'Reconnecting' },
      { value: 'failed', label: 'Failed' },
      { value: 'stop', label: 'Stop?' },
      { value: 'stopped', label: 'Stopped' },
      { value: 'done', label: 'Clips ready' },
    ],
  },
  system: {
    slug: 'system',
    title: 'Loading, errors, not found',
    url: 'loading.tsx · error.tsx · not-found.tsx · global-error.tsx',
    flag: 'new_ui_shell',
    summary: 'Route-level safety net: skeletons, in-shell errors, 404s, a page that is off for this account, and signed-out redirects.',
    states: [
      { value: 'loading', label: 'Route loading' },
      { value: 'error', label: 'Page error' },
      { value: 'not-found', label: 'Page not found' },
      { value: 'project-not-found', label: 'Project not found' },
      { value: 'flag-off', label: 'Not on for you' },
      { value: 'global-error', label: 'Whole app failed' },
      { value: 'public-404', label: 'Public 404' },
    ],
  },
} as const satisfies Record<string, ScreenSpec>;

export type ScreenKey = keyof typeof SCREENS;

/** Reads `?state=` against the allowed list, falling back to the first. */
export function pickState(states: ReadonlyArray<StateOption>, requested: string | undefined): string {
  return states.some((option) => option.value === requested) ? (requested as string) : states[0].value;
}

export interface MockPageProps {
  searchParams: Promise<{ state?: string; theme?: string }>;
}
