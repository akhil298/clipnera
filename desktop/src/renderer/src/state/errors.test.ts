import { describe, expect, it } from 'vitest'
import { reason } from './errors'

describe('reason', () => {
  it('drops what Electron adds to errors from the main process', () => {
    expect(reason(new Error("Error invoking remote method 'agent:models': Error: Sign in to use the AI"))).toBe('Sign in to use the AI')
    expect(reason(new Error("Error invoking remote method 'project:apply': ApiRequestError: Overlap"))).toBe('Overlap')
  })

  it('leaves other messages alone', () => {
    expect(reason(new Error('Select something first'))).toBe('Select something first')
    expect(reason('plain')).toBe('plain')
  })
})
