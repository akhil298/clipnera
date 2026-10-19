import { execFileSync } from 'node:child_process'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

/** ffmpeg is only used to make test files; the app itself never calls it. */
export const hasFfmpeg = (() => {
  try {
    execFileSync('ffmpeg', ['-version'], { stdio: 'ignore' })
    return true
  } catch {
    return false
  }
})()

/** Small sample files: a 1080p clip with sound, a WAV, a WebM (which macOS can't open) and a 20 s clip. */
export function makeTestMedia(): Record<'video' | 'audio' | 'webm' | 'long', string> {
  const dir = mkdtempSync(join(tmpdir(), 'clipnera-media-'))
  const ff = (...args: string[]) => execFileSync('ffmpeg', ['-loglevel', 'error', '-y', ...args])
  const files = { video: join(dir, 'clip.mp4'), audio: join(dir, 'voice.wav'), webm: join(dir, 'clip.webm'), long: join(dir, 'long.mp4') }
  ff('-f', 'lavfi', '-i', 'testsrc2=size=1920x1080:rate=30:duration=3', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', files.video)
  ff('-f', 'lavfi', '-i', 'sine=frequency=220:duration=2', files.audio)
  ff('-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=25:duration=1', '-c:v', 'libvpx-vp9', files.webm)
  ff('-f', 'lavfi', '-i', 'testsrc2=size=1920x1080:rate=30:duration=20', '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', files.long)
  return files
}
