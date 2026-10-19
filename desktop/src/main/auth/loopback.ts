import { createServer, type Server } from 'node:http'
import type { AddressInfo } from 'node:net'

export type CallbackResult = { code: string } | { error: string }

export interface Loopback {
  port: number
  /** Resolves with the first /callback the browser brings back. */
  result: Promise<CallbackResult>
  close(): void
}

const page = (title: string, body: string) =>
  `<!doctype html><meta charset="utf-8"><title>Clipnera Studio</title>` +
  `<body style="font:15px -apple-system,system-ui;display:grid;place-items:center;height:90vh;margin:0;background:#0a0a0a;color:#ededed">` +
  `<div style="text-align:center"><h1 style="font-size:20px">${title}</h1><p style="color:#a3a3a3">${body}</p></div>`

const escape = (text: string) => text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)

/** Listens on 127.0.0.1 at a free port for the browser's return from sign-in. */
export function startLoopback(timeoutMs: number): Promise<Loopback> {
  return new Promise((resolveStart, rejectStart) => {
    let settle: (result: CallbackResult) => void = () => {}
    const result = new Promise<CallbackResult>((resolve) => (settle = resolve))

    const server: Server = createServer((req, res) => {
      const url = new URL(req.url ?? '/', 'http://127.0.0.1')
      if (url.pathname !== '/callback') {
        res.writeHead(404).end()
        return
      }
      const code = url.searchParams.get('code')
      const error = url.searchParams.get('error')
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
      res.end(code ? page("You're signed in", 'You can close this tab and go back to Clipnera Studio.') : page("Sign-in didn't finish", escape(error ?? 'Please try again.')))
      settle(code ? { code } : { error: error ?? 'Sign-in did not finish. Please try again.' })
    })

    const timer = setTimeout(() => settle({ error: 'Sign-in timed out. Please try again.' }), timeoutMs)
    const close = () => {
      clearTimeout(timer)
      server.close()
    }
    void result.then(close)

    server.once('error', rejectStart)
    server.listen(0, '127.0.0.1', () => {
      resolveStart({ port: (server.address() as AddressInfo).port, result, close: () => settle({ error: 'Sign-in was cancelled.' }) })
    })
  })
}
