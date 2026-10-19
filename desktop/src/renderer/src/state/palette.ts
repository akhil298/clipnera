import { createStore } from './store'

export const palette = createStore<{ open: boolean }>({ open: false })
