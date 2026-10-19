import { itemEnd, type ClipItem, type SfxItem, type Timeline } from '@timeline'
import type { AssetResolver } from './player'
import { segments } from './sequence'

export interface MusicCue {
  id: string
  url: string
  start: number
  end: number
  sourceStart: number
  speed: number
  volume: number
}

export interface SoundCue {
  id: string
  url: string
  at: number
  /** 0–1: the item's level under the export's sound-effect level. */
  volume: number
}

export interface MixPlan {
  music: MusicCue | null
  sounds: SoundCue[]
  /** Stretches of the edit with speech under them, where the music ducks (seconds). */
  speech: { start: number; end: number }[]
}

// The export plays sound effects this far under the voice (edit_engine/render.py SFX_GAIN_DB).
const SFX_LEVEL_DB = -12
// The export ducks music hard under speech (sidechaincompress ratio 8); this is about as quiet.
export const DUCKED = 0.3
const DRIFT = 0.3
// A sound whose moment was more than this ago when the playhead crossed it is skipped (a jump, not playback).
const LATE = 0.25

/**
 * What the viewer plays besides the picture, picked the way the export picks it
 * (brain/render_adapter.py): the first audio-track clip of an audio file is the music,
 * ducked under the main track's speech; sound effects play at their start.
 */
export function mixPlan(t: Timeline, resolve: AssetResolver, soundUrl: (item: SfxItem) => string | null): MixPlan {
  const audio = t.tracks.filter((tr) => tr.kind === 'audio' && !tr.muted)
  const musicClip = audio
    .flatMap((tr) => [...tr.items].sort((a, b) => a.at - b.at))
    .find((i): i is ClipItem => i.type === 'clip' && t.assets[i.asset]?.kind === 'audio')
  const musicUrl = musicClip && resolve(musicClip.asset)
  const music =
    musicClip && musicUrl
      ? { id: musicClip.id, url: musicUrl, start: musicClip.at / t.fps, end: itemEnd(musicClip) / t.fps, sourceStart: musicClip.src_in / t.fps, speed: musicClip.speed, volume: musicClip.volume }
      : null
  const sounds = audio
    .flatMap((tr) => tr.items)
    .filter((i): i is SfxItem => i.type === 'sfx')
    .flatMap((i) => {
      const url = soundUrl(i)
      return url ? [{ id: i.id, url, at: i.at / t.fps, volume: Math.min(1, 10 ** ((i.gain_db + SFX_LEVEL_DB) / 20)) }] : []
    })
    .sort((a, b) => a.at - b.at)
  const speech = segments(t)
    .filter((s) => t.assets[s.clip.asset]?.has_audio && s.clip.volume > 0)
    .map((s) => ({ start: s.start, end: s.end }))
  return { music, sounds, speech }
}

export const ducked = (plan: MixPlan, time: number) => plan.speech.some((s) => time >= s.start && time < s.end)

/** Plays a mix plan in step with the viewer's clock. Its audio elements live in `container`. */
export class AudioMix {
  private plan: MixPlan = { music: null, sounds: [], speech: [] }
  private music: HTMLAudioElement | null = null
  private last = 0

  constructor(private readonly container: HTMLElement) {}

  update(plan: MixPlan): void {
    this.plan = plan
    if (this.music && this.music.dataset.cue !== plan.music?.url) {
      this.music.remove()
      this.music = null
    }
  }

  /** Called on every frame the viewer shows. Only normal forward playback is heard. */
  tick(time: number, speed: number): void {
    const playing = speed === 1
    const cue = this.plan.music
    if (cue && playing && time >= cue.start && time < cue.end) {
      const el = this.music ?? (this.music = this.element(cue.url, 'music'))
      const target = cue.sourceStart + (time - cue.start) * cue.speed
      if (Math.abs(el.currentTime - target) > DRIFT) el.currentTime = target
      el.playbackRate = cue.speed
      el.volume = Math.min(1, cue.volume) * (ducked(this.plan, time) ? DUCKED : 1)
      if (el.paused) void el.play().catch(() => undefined)
    } else {
      this.music?.pause()
    }

    // Sounds fire as the playhead passes them; seeking or jumping doesn't set them off.
    if (playing && time > this.last && time - this.last < 0.5) {
      for (const sound of this.plan.sounds) {
        if (sound.at > this.last && sound.at <= time && time - sound.at < LATE) {
          const el = this.element(sound.url, 'sound')
          el.volume = sound.volume
          el.onended = () => el.remove()
          void el.play().catch(() => el.remove())
        }
      }
    }
    this.last = time
  }

  stop(): void {
    this.music?.pause()
    this.container.querySelectorAll('audio[data-role="sound"]').forEach((el) => el.remove())
  }

  private element(url: string, role: 'music' | 'sound'): HTMLAudioElement {
    const el = document.createElement('audio')
    el.src = url
    el.dataset.role = role
    el.dataset.cue = url
    el.preload = 'auto'
    this.container.appendChild(el)
    return el
  }
}
