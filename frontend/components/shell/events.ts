/**
 * Fired (cancelable) on `window` when ⌘K / Ctrl+K is pressed. A page with its
 * own prompt (Home's hero composer) calls `event.preventDefault()` and focuses
 * it; otherwise the shell opens the Go to menu (screens/01 §5.6).
 */
export const PROMPT_FOCUS_EVENT = 'clipnera:prompt-focus';
