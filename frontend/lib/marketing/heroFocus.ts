/** Header, pricing and closing-band buttons ask the hero composer to take focus, so the page has one input. */
const HERO_FOCUS_EVENT = 'cn:focus-hero';

export function focusHeroPrompt(): void {
  window.dispatchEvent(new Event(HERO_FOCUS_EVENT));
}

export function onHeroFocusRequest(listener: () => void): () => void {
  window.addEventListener(HERO_FOCUS_EVENT, listener);
  return () => window.removeEventListener(HERO_FOCUS_EVENT, listener);
}
