const PATHS = {
  media: 'M3 5h18v14H3zM3 9h18M8 5v4M16 5v4',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4',
  sounds: 'M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2',
  broll: 'M3 6h12v12H3zM15 10l6-3v10l-6-3',
  graphics: 'M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M18 6l-2.5 2.5M8.5 15.5L6 18',
  effects: 'M12 3l2.2 5.8L20 11l-5.8 2.2L12 19l-2.2-5.8L4 11l5.8-2.2z',
  text: 'M5 6h14M12 6v13M9 19h6',
  music: 'M9 18V6l11-2v12M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM20 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0z',
  skills: 'M7 4l-4 8 4 8M17 4l4 8-4 8M14 4l-4 16',
  rules: 'M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01',
  takes: 'M6 3v12M6 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 9c0 6-12 3-12 6',
  spark: 'M12 2l1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8z',
  play: 'M7 5l12 7-12 7z',
  pause: 'M8 5v14M16 5v14',
  back: 'M19 5v14L8 12zM6 5v14',
  forward: 'M5 5v14l11-7zM18 5v14',
  send: 'M5 12h14M13 6l6 6-6 6'
} as const

export type IconName = keyof typeof PATHS

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  )
}
