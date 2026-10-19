import { createHash } from 'node:crypto'
import { describe, expect, it } from 'vitest'
import { challengeFor, createVerifier } from './pkce'

describe('pkce', () => {
  it('makes 43-character base64url verifiers that differ every time', () => {
    const a = createVerifier()
    expect(a).toMatch(/^[A-Za-z0-9_-]{43}$/)
    expect(createVerifier()).not.toBe(a)
  })

  it('makes the S256 challenge the backend expects', () => {
    const verifier = createVerifier()
    const expected = createHash('sha256').update(verifier).digest('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
    expect(challengeFor(verifier)).toBe(expected)
    expect(challengeFor(verifier)).toHaveLength(43)
  })
})
