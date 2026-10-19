import { useEffect, useState } from 'react'
import type { AppInfo } from '../../../shared/ipc'

let cached: Promise<AppInfo> | undefined

/** App name, version and website; fetched once from the main process. */
export function useAppInfo(): AppInfo | undefined {
  const [info, setInfo] = useState<AppInfo>()
  useEffect(() => {
    cached ??= window.clipnera.appInfo()
    void cached.then(setInfo)
  }, [])
  return info
}
