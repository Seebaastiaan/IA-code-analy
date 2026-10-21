import { Fragment, type ReactNode } from 'react'

function inline(line: string): ReactNode[] {
  return line.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).map((p, i) => {
    if (p.length > 1 && p.startsWith('`') && p.endsWith('`')) return <code key={i}>{p.slice(1, -1)}</code>
    if (p.length > 3 && p.startsWith('**') && p.endsWith('**')) return <b key={i}>{p.slice(2, -2)}</b>
    return p
  })
}

/**
 * Markdown mínimo y seguro para respuestas del asistente: `código`, **negrita** y saltos de línea.
 * No usa innerHTML: el contenido del servidor nunca se interpreta como HTML.
 */
export function MiniMarkdown({ text }: { text: string }) {
  const lines = text.split('\n')
  return (
    <>
      {lines.map((line, i) => (
        <Fragment key={i}>
          {inline(line)}
          {i < lines.length - 1 && <br />}
        </Fragment>
      ))}
    </>
  )
}
