import { mkdtemp } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { beforeEach, describe, expect, it } from 'vitest'
import type { DesktopExchangeRequest, DesktopStartRequest, UserProfileResponse } from '../../shared/api'
import type { AuthState } from '../../shared/ipc'
import { ApiRequestError, type api as Api } from '../api'
import { challengeFor } from './pkce'
import { AuthSession } from './session'
import { TokenStore } from './tokenStore'

const user = { id: 'user-1', name: 'Akhil', email: 'a@example.com', plan: 'pro', ai_credits_minutes_remaining: 1240 } as UserProfileResponse
const identity = { encrypt: (t: string) => Buffer.from(t), decrypt: (d: Buffer) => d.toString() }

/** A backend that checks the PKCE pair like the real one, and a "browser" that follows the redirect. */
function fakeBackend(callbackQuery = 'code=one-time') {
  const calls: string[] = []
  let challenge = ''
  const api = {
    async postData(path: string, body: unknown) {
      calls.push(path)
      if (path === '/auth/desktop/start') {
        const start = body as DesktopStartRequest
        challenge = start.code_challenge
        return { authorize_url: `http://127.0.0.1:${start.redirect_port}/callback?${callbackQuery}` }
      }
      const exchange = body as DesktopExchangeRequest
      if (exchange.code !== 'one-time' || challengeFor(exchange.code_verifier) !== challenge) throw new ApiRequestError(400, 'DESKTOP_CODE_INVALID', 'bad code')
      return { access_token: 'token-1', token_type: 'bearer', expires_in: 3600 }
    },
    async get(path: string, token?: string) {
      calls.push(path)
      if (token !== 'token-1') throw new ApiRequestError(401, 'UNAUTHORIZED', 'expired')
      return user
    },
    async post(path: string) {
      calls.push(path)
      return {}
    }
  }
  return { api: api as unknown as typeof Api, calls }
}

describe('AuthSession', () => {
  let store: TokenStore
  let states: AuthState[]

  beforeEach(async () => {
    store = new TokenStore(join(await mkdtemp(join(tmpdir(), 'clipnera-')), 'session.bin'), identity)
    states = []
  })

  const session = (backend: ReturnType<typeof fakeBackend>, openBrowser: (url: string) => Promise<void> = async (url) => void (await fetch(url))) =>
    new AuthSession({ api: backend.api, store, openBrowser, onChange: (s) => states.push(s) })

  it('signs in through the browser and keeps the session', async () => {
    const backend = fakeBackend()
    const auth = session(backend)
    await auth.signIn(true)

    expect(states.map((s) => s.status)).toEqual(['waiting', 'signedIn'])
    expect(auth.get()).toEqual({ status: 'signedIn', user })
    expect(backend.calls).toEqual(['/auth/desktop/start', '/auth/desktop/exchange', '/me'])
    expect((await store.load())?.accessToken).toBe('token-1')
  })

  it('shows the reason when Google sign-in fails', async () => {
    await session(fakeBackend('error=Google+sign-in+was+cancelled.')).signIn(true)
    expect(states.at(-1)).toEqual({ status: 'signedOut', error: 'Google sign-in was cancelled.' })
    expect(await store.load()).toBeNull()
  })

  it('cancelling goes back quietly', async () => {
    let auth: AuthSession
    auth = session(fakeBackend(), async () => auth.cancel())
    await auth.signIn(true)
    expect(states.at(-1)).toEqual({ status: 'signedOut', error: undefined })
  })

  it('reports an unreachable backend', async () => {
    const backend = fakeBackend()
    backend.api.postData = async () => { throw new ApiRequestError(0, 'OFFLINE', "Can't reach Clipnera.") }
    await session(backend).signIn(true)
    expect(states.at(-1)).toEqual({ status: 'signedOut', error: "Can't reach Clipnera." })
  })

  it('restores a saved session on launch', async () => {
    await store.save({ accessToken: 'token-1', expiresAt: Date.now() + 60_000 })
    const auth = session(fakeBackend())
    await auth.restore()
    expect(auth.get()).toEqual({ status: 'signedIn', user })
  })

  it('forgets a session the backend no longer accepts', async () => {
    await store.save({ accessToken: 'revoked', expiresAt: Date.now() + 60_000 })
    const auth = session(fakeBackend())
    await auth.restore()
    expect(auth.get()).toEqual({ status: 'signedOut', error: undefined })
    expect(await store.load()).toBeNull()
  })

  it('signs out and tells the backend', async () => {
    const backend = fakeBackend()
    const auth = session(backend)
    await auth.signIn(true)
    await auth.signOut()
    expect(auth.get()).toEqual({ status: 'signedOut' })
    expect(backend.calls.at(-1)).toBe('/auth/logout')
    expect(await store.load()).toBeNull()
  })
})
