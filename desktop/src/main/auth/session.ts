import type { DesktopExchangeRequest, DesktopStartRequest, DesktopStartResponse, TokenResponse, UserProfileResponse } from '../../shared/api'
import type { AuthState } from '../../shared/ipc'
import { ApiRequestError, type api as Api } from '../api'
import { startLoopback, type Loopback } from './loopback'
import { challengeFor, createVerifier } from './pkce'
import type { TokenStore } from './tokenStore'

const SIGN_IN_TIMEOUT_MS = 5 * 60_000

export interface AuthSessionDeps {
  api: typeof Api
  store: TokenStore
  openBrowser(url: string): Promise<void>
  onChange(state: AuthState): void
}

const message = (error: unknown) => (error instanceof Error ? error.message : 'Sign-in failed. Please try again.')

/** The signed-in account: restores it on launch, signs in through the browser, signs out. */
export class AuthSession {
  private state: AuthState = { status: 'loading' }
  private pending: Loopback | null = null
  private cancelled = false

  constructor(private readonly deps: AuthSessionDeps) {}

  get(): AuthState {
    return this.state
  }

  async restore(): Promise<void> {
    const session = await this.deps.store.load()
    if (!session) return this.set({ status: 'signedOut' })
    try {
      this.set({ status: 'signedIn', user: await this.profile(session.accessToken) })
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 401) await this.deps.store.clear()
      this.set({ status: 'signedOut', error: error instanceof ApiRequestError && error.status === 401 ? undefined : message(error) })
    }
  }

  async signIn(acceptTerms: boolean): Promise<void> {
    if (this.state.status === 'waiting') return
    this.cancelled = false
    this.set({ status: 'waiting' })
    const verifier = createVerifier()
    const loopback = (this.pending = await startLoopback(SIGN_IN_TIMEOUT_MS))

    try {
      const start = await this.deps.api.postData<DesktopStartResponse>('/auth/desktop/start', {
        code_challenge: challengeFor(verifier),
        redirect_port: loopback.port,
        accept_terms: acceptTerms
      } satisfies DesktopStartRequest)
      await this.deps.openBrowser(start.authorize_url)

      const result = await loopback.result
      if ('error' in result) return this.set({ status: 'signedOut', error: this.cancelled ? undefined : result.error })

      const token = await this.deps.api.postData<TokenResponse>('/auth/desktop/exchange', {
        code: result.code,
        code_verifier: verifier
      } satisfies DesktopExchangeRequest)
      await this.deps.store.save({ accessToken: token.access_token, expiresAt: Date.now() + token.expires_in * 1000 })
      this.set({ status: 'signedIn', user: await this.profile(token.access_token) })
    } catch (error) {
      this.set({ status: 'signedOut', error: message(error) })
    } finally {
      loopback.close()
      this.pending = null
    }
  }

  /** The saved access token, or null when signed out or expired. */
  async token(): Promise<string | null> {
    return (await this.deps.store.load())?.accessToken ?? null
  }

  cancel(): void {
    this.cancelled = true
    this.pending?.close()
  }

  async signOut(): Promise<void> {
    const session = await this.deps.store.load()
    await this.deps.store.clear()
    this.set({ status: 'signedOut' })
    // Best effort: the session is gone from this Mac either way.
    if (session) await this.deps.api.post('/auth/logout', {}, session.accessToken).catch(() => undefined)
  }

  private profile(token: string): Promise<UserProfileResponse> {
    return this.deps.api.get<UserProfileResponse>('/me', token)
  }

  private set(state: AuthState): void {
    this.state = state
    this.deps.onChange(state)
  }
}
