const AUTH_STORAGE_KEY = 'token';
const TOKEN_EXPIRY_KEY = 'token_expires_at';

export interface AuthState {
  token: string | null;
  expiresAt: number | null;
}

export function getAuth(): AuthState {
  if (typeof window === 'undefined') return { token: null, expiresAt: null };

  try {
    const token = localStorage.getItem(AUTH_STORAGE_KEY);
    const expiresAtStr = localStorage.getItem(TOKEN_EXPIRY_KEY);
    const expiresAt = expiresAtStr ? Number(expiresAtStr) : null;
    return { token, expiresAt };
  } catch {
    return { token: null, expiresAt: null };
  }
}

export function setAuth(token: string, expiresInSeconds: number): void {
  if (typeof window === 'undefined') return;
  const expiresAt = Date.now() + expiresInSeconds * 1000;
  localStorage.setItem(AUTH_STORAGE_KEY, token);
  localStorage.setItem(TOKEN_EXPIRY_KEY, String(expiresAt));
}

export function clearAuth(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(AUTH_STORAGE_KEY);
  localStorage.removeItem(TOKEN_EXPIRY_KEY);
}

export function isTokenExpired(): boolean {
  const { expiresAt } = getAuth();
  if (!expiresAt) return false;
  return Date.now() >= expiresAt;
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

export function getToken(): string | null {
  const { token, expiresAt } = getAuth();
  if (!token) return null;
  if (expiresAt !== null && (Number.isNaN(expiresAt) || Date.now() >= expiresAt)) {
    clearAuth();
    return null;
  }
  return token;
}
