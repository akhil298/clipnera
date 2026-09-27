const GOOGLE_AUTHORIZE_URL = 'https://accounts.google.com/o/oauth2/v2/auth';
const STATE_STORAGE_KEY = 'google_oauth_state';

/** Where Google sends the user back to; must be listed in the Google Cloud console. */
export const GOOGLE_CALLBACK_PATH = '/login/google';

export function googleRedirectUri(): string {
  return `${window.location.origin}${GOOGLE_CALLBACK_PATH}`;
}

/** Send the browser to Google's consent screen. */
export function startGoogleSignIn(): void {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  if (!clientId) throw new Error('Google sign-in is not configured.');

  const state = crypto.randomUUID();
  sessionStorage.setItem(STATE_STORAGE_KEY, state);

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: googleRedirectUri(),
    response_type: 'code',
    scope: 'openid email profile',
    state,
    prompt: 'select_account',
  });
  window.location.assign(`${GOOGLE_AUTHORIZE_URL}?${params}`);
}

/** True when `state` is the one this tab sent to Google; it can only be used once. */
export function consumeGoogleState(state: string): boolean {
  const expected = sessionStorage.getItem(STATE_STORAGE_KEY);
  sessionStorage.removeItem(STATE_STORAGE_KEY);
  return !!expected && expected === state;
}
