import { useEffect } from 'react'
import { MEDIA_COMMANDS } from '../../../shared/commands'
import { runCommand } from '.'

/** Files dropped anywhere on the window are imported; nothing else happens on a drop. */
export function useFileDrop(): void {
  useEffect(() => {
    const onDragOver = (event: DragEvent) => event.preventDefault()
    const onDrop = (event: DragEvent) => {
      event.preventDefault()
      const paths = [...(event.dataTransfer?.files ?? [])].map((file) => window.clipnera.media.pathForFile(file)).filter(Boolean)
      if (paths.length) runCommand(MEDIA_COMMANDS.import, { paths })
    }
    window.addEventListener('dragover', onDragOver)
    window.addEventListener('drop', onDrop)
    return () => {
      window.removeEventListener('dragover', onDragOver)
      window.removeEventListener('drop', onDrop)
    }
  }, [])
}
