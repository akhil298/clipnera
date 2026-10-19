import { reason } from './errors'
import { createStore } from './store'

const MAX_MS = 60_000

/** A voice note for the chat: recording, then what was said, which lands in the composer. */
export const voice = createStore<{
  state: 'idle' | 'recording' | 'reading'
  startedAt: number
  /** The latest transcript, with a counter so the composer knows a new one arrived. */
  heard: { text: string; seq: number } | null
  error: string | null
}>({ state: 'idle', startedAt: 0, heard: null, error: null })

let recorder: MediaRecorder | null = null
let stopTimer: ReturnType<typeof setTimeout> | undefined

export async function startVoice(): Promise<void> {
  if (voice.get().state !== 'idle') return
  let stream: MediaStream
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch {
    voice.set({ error: 'Clipnera Studio needs the microphone: allow it in System Settings → Privacy & Security → Microphone.' })
    return
  }
  const chunks: Blob[] = []
  const rec = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
  recorder = rec
  rec.ondataavailable = (e) => e.data.size && chunks.push(e.data)
  rec.onstop = async () => {
    clearTimeout(stopTimer)
    stream.getTracks().forEach((t) => t.stop())
    const seconds = Math.max(0.5, (Date.now() - voice.get().startedAt) / 1000)
    voice.set({ state: 'reading' })
    try {
      const blob = new Blob(chunks, { type: 'audio/webm' })
      const text = await window.clipnera.agent.transcribe(new Uint8Array(await blob.arrayBuffer()), 'audio/webm', Math.min(60, seconds))
      voice.set({ state: 'idle', error: text ? null : "I didn't hear anything. Try again a little closer to the mic.", heard: text ? { text, seq: (voice.get().heard?.seq ?? 0) + 1 } : voice.get().heard })
    } catch (error) {
      voice.set({ state: 'idle', error: reason(error) })
    }
  }
  rec.start()
  voice.set({ state: 'recording', startedAt: Date.now(), error: null })
  stopTimer = setTimeout(stopVoice, MAX_MS)
}

export function stopVoice(): void {
  if (recorder?.state === 'recording') recorder.stop()
  recorder = null
}

export const toggleVoice = () => (voice.get().state === 'recording' ? stopVoice() : startVoice())
