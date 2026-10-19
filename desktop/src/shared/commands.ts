/** Ids of commands that the native menu can run. The renderer registers the commands themselves. */
export const MEDIA_COMMANDS = {
  import: 'media.import'
} as const

export const EXPORT_COMMANDS = {
  video: 'export.video'
} as const

export const EDIT_COMMANDS = {
  undo: 'edit.undo',
  redo: 'edit.redo',
  split: 'timeline.split',
  delete: 'timeline.delete'
} as const

export const VIEW_COMMANDS = {
  palette: 'view.palette',
  toggleSidePanel: 'view.toggleSidePanel',
  toggleBottomPanel: 'view.toggleBottomPanel',
  toggleAiPanel: 'view.toggleAiPanel'
} as const
