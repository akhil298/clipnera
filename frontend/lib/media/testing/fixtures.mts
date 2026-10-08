// A small Timeline v1 for the playback tests: 30 fps, 9:16, two picture clips with a
// fade between them, a B-roll cutaway, a hook, a voice track, music and one sound effect.
import type { Timeline } from '../../editor/timeline.ts';

const T = { x: 0.5, y: 0.5, scale: 1, rotation: 0 };

export const timeline: Timeline = {
  version: 1, fps: 30, width: 1080, height: 1920, look: 'natural',
  assets: {
    a: { id: 'a', kind: 'video', key: 'k/a', proxy: 'p/a', frames: 900, width: 1920, height: 1080, has_audio: true },
    b: { id: 'b', kind: 'video', key: 'k/b', proxy: null, frames: 900, width: 1080, height: 1920, has_audio: false },
    img: { id: 'img', kind: 'image', key: 'k/img', proxy: null, frames: 1, width: 1000, height: 1000, has_audio: false },
    vo: { id: 'vo', kind: 'audio', key: 'k/vo', proxy: null, frames: 900, width: null, height: null, has_audio: true },
  },
  tracks: [
    { id: 'v1', kind: 'video', muted: false, items: [
      { type: 'clip', id: 'c1', at: 0, asset: 'a', src_in: 30, src_out: 120, speed: 1, volume: 1, transform: T,
        keyframes: { scale: [{ f: 0, v: 1, ease: 'linear' }, { f: 60, v: 1.5, ease: 'linear' }] }, transition_in: null },
      { type: 'clip', id: 'c2', at: 90, asset: 'b', src_in: 0, src_out: 120, speed: 2, volume: 1, transform: T,
        keyframes: {}, transition_in: { type: 'slide_left', frames: 10 } },
    ] },
    { id: 'ov', kind: 'overlay', muted: false, items: [
      { type: 'clip', id: 'br', at: 30, asset: 'img', src_in: 0, src_out: 30, speed: 1, volume: 1, transform: T, keyframes: {}, transition_in: null },
    ] },
    { id: 'hook', kind: 'text', muted: false, items: [
      { type: 'text', id: 'h0', at: 0, text: 'Watch this', style: 'hook', dur: 60, transform: { ...T, y: 0.2 } },
    ] },
    { id: 'voice', kind: 'audio', muted: false, items: [
      { type: 'clip', id: 'vo1', at: 0, asset: 'vo', src_in: 0, src_out: 150, speed: 1, volume: 0.8, transform: T, keyframes: {}, transition_in: null },
    ] },
    { id: 'sfx', kind: 'audio', muted: false, items: [{ type: 'sfx', id: 'fx0', at: 45, name: 'whoosh', dur: 15, gain_db: -6 }] },
    { id: 'music', kind: 'audio', muted: false, items: [
      { type: 'music', id: 'm0', at: 0, track: 'lofi', dur: 150, offset: 60, gain_db: -20, duck: true },
    ] },
  ],
  captions: { enabled: true, style: 'karaoke', language: 'en', follow: 'voice' },
  markers: [],
};
