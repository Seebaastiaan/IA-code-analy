const PATHS = {
  flow: 'M4 5h5v5H4zM15 5h5v5h-5zM9.5 14h5v5h-5zM9 7.5h6M12 10v4',
  home: 'M3 11l9-7 9 7M5 10v10h5v-6h4v6h5V10',
  plus: 'M12 5v14M5 12h14',
  folder: 'M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z',
  doc: 'M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6',
  code: 'M8 9l-4 3 4 3M16 9l4 3-4 3M13.5 6l-3 12',
  chat: 'M4 5h16v11H9l-5 4zM8 9h8M8 12h5',
  compare: 'M8 4v16M16 4v16M4 8h8M12 16h8',
  sliders: 'M4 6h9M17 6h3M15 4v4M4 12h3M11 12h9M9 10v4M4 18h11M19 18h1M17 16v4',
  lock: 'M6 11h12v9H6zM8 11V7a4 4 0 018 0v4',
  globe: 'M12 3a9 9 0 100 18 9 9 0 000-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18',
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM9 12l2 2 4-4',
  beaker: 'M9 3h6M10 3v6L4.5 18.5A1.5 1.5 0 005.8 21h12.4a1.5 1.5 0 001.3-2.5L14 9V3M7 15h10',
  sparkle: 'M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8zM18.5 14.5l.8 1.7 1.7.8-1.7.8-.8 1.7-.8-1.7-1.7-.8 1.7-.8z',
  share: 'M4 13v6h16v-6M12 3v12M8 7l4-4 4 4',
  download: 'M12 3v12M8 11l4 4 4-4M4 19h16',
  sun: 'M12 8a4 4 0 100 8 4 4 0 000-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  moon: 'M20 13.5A8 8 0 1110.5 4a6.5 6.5 0 009.5 9.5z',
  menu: 'M4 6h16M4 12h16M4 18h16',
  x: 'M6 6l12 12M18 6L6 18',
  search: 'M11 4a7 7 0 100 14 7 7 0 000-14zM20 20l-4-4',
  check: 'M5 12.5l4.5 4.5L19 7',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  chevron: 'M9 6l6 6-6 6',
  refresh: 'M4 4v6h6M20 20v-6h-6M5.5 15a7 7 0 0012 2.5M18.5 9A7 7 0 006.5 6.5',
  copy: 'M9 9h11v11H9zM5 15V4h11',
  send: 'M4 12L20 4l-6 16-2.5-6.5z',
  wand: 'M4 20L15 9M17 3v3M20 6h-3M14 5l1 1M19 10l1 1',
  eye: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 9a3 3 0 100 6 3 3 0 000-6z',
  branch: 'M6 3v12M18 9a3 3 0 100-6 3 3 0 000 6zM6 21a3 3 0 100-6 3 3 0 000 6zM18 9c0 5-12 2-12 6',
  file: 'M7 3h7l5 5v13H7zM14 3v5h5',
  alert: 'M12 9v4M12 17h.01M10.3 3.9L2.4 18a2 2 0 001.7 3h15.8a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z',
  clock: 'M12 3a9 9 0 100 18 9 9 0 000-18zM12 7v5l3 2',
  play: 'M7 5l12 7-12 7z',
  ban: 'M12 3a9 9 0 100 18 9 9 0 000-18zM5.6 5.6l12.8 12.8',
  bolt: 'M13 3L5 13h6l-1 8 8-10h-6z',
  save: 'M5 3h11l3 3v15H5zM8 3v5h7V3M8 21v-7h8v7',
  diff: 'M8 4v10M3 9h10M16 13v7M11 17h10',
  users: 'M16 20v-1.5a4 4 0 00-4-4H7a4 4 0 00-4 4V20M9.5 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM21 20v-1.5a4 4 0 00-3-3.87M16 4.13a3.5 3.5 0 010 6.74',
} as const

export type IconName = keyof typeof PATHS

export function Icon({ name, className = 'w-5 h-5' }: { name: IconName; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  )
}
