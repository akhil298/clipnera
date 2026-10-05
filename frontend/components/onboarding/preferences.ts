/**
 * First-run answers (screens/01 §4).
 *
 * NEEDS-BACKEND: PATCH /me/preferences {creator_types, platforms, onboarding_completed_at}
 * and `onboarding_completed_at` on GET /me (API-3). Until then the answers live
 * in this browser, keyed by account, so "shown once" holds per account per device.
 */

export const CREATOR_TYPES = [
  'Podcasts',
  'Interviews',
  'Talking-head videos',
  'Tutorials and courses',
  'Streams and gaming',
  'Vlogs',
  'Webinars and talks',
  'Something else',
] as const;

export type CreatorType = (typeof CREATOR_TYPES)[number];

export interface OnboardingAnswers {
  creator_types: CreatorType[];
  /** ISO time; set whether the person finished or skipped. */
  onboarding_completed_at: string;
}

const keyFor = (userId: string) => `cn.onboarding:${userId}`;

/** The saved answers, or null when this account hasn't been through the welcome on this device. */
export function readOnboarding(userId: string): OnboardingAnswers | null {
  try {
    const raw = localStorage.getItem(keyFor(userId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<OnboardingAnswers>;
    if (typeof parsed.onboarding_completed_at !== 'string') return null;
    const types = Array.isArray(parsed.creator_types) ? parsed.creator_types : [];
    return {
      onboarding_completed_at: parsed.onboarding_completed_at,
      creator_types: types.filter((type): type is CreatorType => (CREATOR_TYPES as readonly string[]).includes(type)),
    };
  } catch {
    return null;
  }
}

/** False when the browser refused storage: the welcome may then show again next time, as the spec allows. */
export function saveOnboarding(userId: string, creatorTypes: readonly CreatorType[]): boolean {
  const answers: OnboardingAnswers = { creator_types: [...creatorTypes], onboarding_completed_at: new Date().toISOString() };
  try {
    localStorage.setItem(keyFor(userId), JSON.stringify(answers));
    return true;
  } catch {
    return false;
  }
}
