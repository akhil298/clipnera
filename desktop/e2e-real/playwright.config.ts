import { defineConfig } from '@playwright/test'

/** The real end-to-end run: a live backend and real AI. Not part of `npm run test:e2e`. */
export default defineConfig({ testDir: '.', timeout: 30 * 60_000, workers: 1, reporter: 'line' })
