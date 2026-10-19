import { describe, expect, it } from 'vitest'
import { startLoopback } from './loopback'

describe('startLoopback', () => {
  it('hands back the code from /callback and shows a done page', async () => {
    const loopback = await startLoopback(5_000)
    const response = await fetch(`http://127.0.0.1:${loopback.port}/callback?code=abc`)
    expect(await response.text()).toContain("You're signed in")
    expect(await loopback.result).toEqual({ code: 'abc' })
  })

  it('reports errors without echoing markup', async () => {
    const loopback = await startLoopback(5_000)
    const page = await (await fetch(`http://127.0.0.1:${loopback.port}/callback?error=${encodeURIComponent('<b>no</b>')}`)).text()
    expect(page).not.toContain('<b>no</b>')
    expect(await loopback.result).toEqual({ error: '<b>no</b>' })
  })

  it('ignores other paths, then times out', async () => {
    const loopback = await startLoopback(50)
    expect((await fetch(`http://127.0.0.1:${loopback.port}/favicon.ico`)).status).toBe(404)
    expect(await loopback.result).toEqual({ error: 'Sign-in timed out. Please try again.' })
  })

  it('can be cancelled', async () => {
    const loopback = await startLoopback(5_000)
    loopback.close()
    expect(await loopback.result).toEqual({ error: 'Sign-in was cancelled.' })
  })
})
