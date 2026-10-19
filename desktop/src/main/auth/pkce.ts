import { createHash, randomBytes } from 'node:crypto'

/** 32 random bytes as base64url: a 43-character PKCE verifier. */
export function createVerifier(): string {
  return randomBytes(32).toString('base64url')
}

/** S256 challenge: base64url(sha256(verifier)), no padding. */
export function challengeFor(verifier: string): string {
  return createHash('sha256').update(verifier).digest('base64url')
}
