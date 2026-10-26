import { loader } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'
import EditorWorker from 'monaco-editor/editor/editor.worker?worker'
import { useEffect } from 'react'
import { useTheme } from '@/shared/hooks/useTheme'

// Monaco se empaqueta con la app (no desde CDN) para que funcione sin internet o detrás del túnel.
// Python, TOML y Markdown solo usan coloreado Monarch, así que basta con el worker base.
self.MonacoEnvironment = { getWorker: () => new EditorWorker() }
loader.config({ monaco })

const DARK = 'iavoy-dark'
const LIGHT = 'iavoy-light'

/** Lee un color de la paleta activa (globals.css). Monaco necesita hex, así que solo se usa en modo oscuro. */
function paletteColor(name: string, fallback: string) {
  if (!document.documentElement.classList.contains('dark')) return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return /^#[0-9a-f]{6}$/i.test(v) ? v : fallback
}

/** Temas del editor alineados con la paleta de la app (fondo = tarjeta, números de línea = texto tenue). */
export function defineEditorThemes() {
  monaco.editor.defineTheme(DARK, {
    base: 'vs-dark',
    inherit: true,
    rules: [],
    colors: {
      'editor.background': paletteColor('--color-slate-900', '#22272e'),
      'editorGutter.background': paletteColor('--color-slate-900', '#22272e'),
      'editor.lineHighlightBackground': paletteColor('--color-slate-800', '#2d333b'),
      'editor.lineHighlightBorder': '#00000000',
      'editorLineNumber.foreground': paletteColor('--color-slate-600', '#545d68'),
      'editorLineNumber.activeForeground': paletteColor('--color-slate-300', '#adbac7'),
      'editorWidget.background': paletteColor('--color-slate-800', '#2d333b'),
      'editor.selectionBackground': '#7060f155',
      'scrollbarSlider.background': paletteColor('--color-slate-700', '#3d444d') + '99',
    },
  })
  monaco.editor.defineTheme(LIGHT, {
    base: 'vs',
    inherit: true,
    rules: [],
    colors: {
      'editor.background': '#ffffff',
      'editor.lineHighlightBackground': '#f8fafc',
      'editor.lineHighlightBorder': '#00000000',
      'editorLineNumber.foreground': '#94a3b8',
      'editorLineNumber.activeForeground': '#475569',
      'editor.selectionBackground': '#cbc9ff99',
    },
  })
}

/** Nombre del tema de Monaco según el tema de la app; lo redefine al alternar claro/oscuro. */
export function useEditorTheme() {
  const theme = useTheme((s) => s.theme)
  const name = theme === 'dark' ? DARK : LIGHT
  useEffect(() => {
    defineEditorThemes()
    monaco.editor.setTheme(name)
  }, [name])
  return name
}
