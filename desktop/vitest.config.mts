import { resolve } from 'node:path'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  resolve: { alias: { '@timeline': resolve(import.meta.dirname, '../frontend/lib/editor/timeline.ts') } },
  test: { include: ['src/**/*.test.ts'], environment: 'node' }
})
