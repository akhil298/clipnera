import { Menu, type MenuItemConstructorOptions } from 'electron'
import { EDIT_COMMANDS, EXPORT_COMMANDS, MEDIA_COMMANDS, VIEW_COMMANDS } from '../shared/commands'

/**
 * The macOS menu bar. View items run workbench commands instead of acting here, so the menu, the keyboard
 * and the AI all go through the same command. Their shortcuts live in the workbench's keybindings, so the
 * items carry no accelerators of their own (a menu accelerator would swallow the key first).
 */
export function buildMenu(runCommand: (commandId: string) => void): Menu {
  const command = (label: string, id: string): MenuItemConstructorOptions => ({ label, click: () => runCommand(id) })

  return Menu.buildFromTemplate([
    { role: 'appMenu' },
    { label: 'File', submenu: [command('Import Media…', MEDIA_COMMANDS.import), command('Export Video…', EXPORT_COMMANDS.video), { type: 'separator' }, { role: 'close' }] },
    {
      label: 'Edit',
      submenu: [
        command('Undo', EDIT_COMMANDS.undo),
        command('Redo', EDIT_COMMANDS.redo),
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' },
        { type: 'separator' },
        command('Split at Playhead', EDIT_COMMANDS.split),
        command('Delete', EDIT_COMMANDS.delete)
      ]
    },
    {
      label: 'View',
      submenu: [
        command('Show All Commands…', VIEW_COMMANDS.palette),
        { type: 'separator' },
        command('Toggle Side Panel', VIEW_COMMANDS.toggleSidePanel),
        command('Toggle Bottom Panel', VIEW_COMMANDS.toggleBottomPanel),
        command('Toggle AI Panel', VIEW_COMMANDS.toggleAiPanel),
        { type: 'separator' },
        { role: 'togglefullscreen' },
        { role: 'toggleDevTools' }
      ]
    },
    { role: 'windowMenu' }
  ])
}
