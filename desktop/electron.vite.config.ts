import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'electron-vite'
import type { Plugin } from 'vite'

// Production builds load from file://, where response headers can't carry a CSP, so it goes in a meta tag.
// Dev skips it: Vite's hot reload injects inline scripts.
const CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data: blob: clipnera-media:; media-src 'self' blob: clipnera-media: http: https:"

function contentSecurityPolicy(): Plugin {
  return {
    name: 'clipnera-csp',
    apply: 'build',
    transformIndexHtml: (html) =>
      html.replace('<head>', `<head>\n    <meta http-equiv="Content-Security-Policy" content="${CSP}" />`)
  }
}

// Timeline v1 and its ops, shared with the backend's own fixtures (frontend/lib/editor/timeline.ts).
export const TIMELINE = resolve(__dirname, '../frontend/lib/editor/timeline.ts')
const alias = { '@timeline': TIMELINE }

export default defineConfig({
  main: { resolve: { alias } },
  preload: {},
  renderer: {
    resolve: { alias },
    server: { fs: { allow: ['.', TIMELINE] } },
    plugins: [react(), contentSecurityPolicy()]
  }
})
