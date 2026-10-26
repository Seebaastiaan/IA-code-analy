import Editor, { DiffEditor, type OnMount } from '@monaco-editor/react'
import { useEffect, useRef } from 'react'
import type { Finding } from '@/features/findings/types'
import { Spinner } from '@/shared/ui'
import { defineEditorThemes, useEditorTheme } from '../monaco'

type CodeEditorInstance = Parameters<OnMount>[0]

const OPTIONS = {
  fontFamily: "'JetBrains Mono', ui-monospace, monospace",
  fontSize: 13,
  lineHeight: 22,
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  glyphMargin: true,
  automaticLayout: true,
  renderLineHighlight: 'line' as const,
  padding: { top: 8, bottom: 8 },
}

const loading = (
  <div className="grid place-items-center h-full text-slate-400">
    <Spinner className="w-5 h-5" />
  </div>
)

interface CodeEditorProps {
  path: string
  language: string
  value: string
  onChange: (value: string) => void
  /** Hallazgos abiertos del archivo: se marcan en la línea y en el margen */
  findings: Finding[]
  /** Línea a la que se desplaza al abrir */
  revealLine?: number
}

export function CodeEditor({ path, language, value, onChange, findings, revealLine }: CodeEditorProps) {
  const theme = useEditorTheme()
  const editorRef = useRef<CodeEditorInstance | null>(null)
  const decorations = useRef<ReturnType<CodeEditorInstance['createDecorationsCollection']> | null>(null)

  const paint = () => {
    const ed = editorRef.current
    if (!ed) return
    decorations.current?.clear()
    decorations.current = ed.createDecorationsCollection(
      findings.map((f) => ({
        range: { startLineNumber: f.line, startColumn: 1, endLineNumber: f.line, endColumn: 1 },
        options: {
          isWholeLine: true,
          className: `iv-line-${f.sev}`,
          glyphMarginClassName: `iv-glyph-${f.sev}`,
          glyphMarginHoverMessage: { value: `**${f.rule}** · ${f.msg}` },
          hoverMessage: { value: `**${f.rule}** · ${f.msg}` },
        },
      })),
    )
  }

  const reveal = (line?: number) => {
    const ed = editorRef.current
    if (!ed || !line) return
    ed.revealLineInCenter(line)
    ed.setPosition({ lineNumber: line, column: 1 })
    ed.focus()
  }

  const onMount: OnMount = (ed) => {
    editorRef.current = ed
    paint()
    reveal(revealLine)
  }

  // Las marcas se recalculan al cambiar de archivo o de hallazgos, no en cada tecla
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(paint, [findings, path])
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => reveal(revealLine), [revealLine, path])

  return (
    <Editor
      height="60vh"
      path={path}
      language={language}
      value={value}
      theme={theme}
      beforeMount={defineEditorThemes}
      onChange={(v) => onChange(v ?? '')}
      onMount={onMount}
      options={OPTIONS}
      loading={loading}
    />
  )
}

export function CodeDiff({ path, language, original, modified }: { path: string; language: string; original: string; modified: string }) {
  const theme = useEditorTheme()
  return (
    <DiffEditor
      height="60vh"
      language={language}
      original={original}
      modified={modified}
      originalModelPath={`original/${path}`}
      modifiedModelPath={`propuesta/${path}`}
      theme={theme}
      beforeMount={defineEditorThemes}
      options={{ ...OPTIONS, readOnly: true, renderSideBySide: true, useInlineViewWhenSpaceIsLimited: true }}
      loading={loading}
    />
  )
}
