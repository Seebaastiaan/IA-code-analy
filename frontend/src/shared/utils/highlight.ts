export interface Token {
  text: string
  cls?: 'tok-s' | 'tok-c' | 'tok-k' | 'tok-n'
}

const RE = /("[^"]*"|'[^']*')|(#.*$)|\b(def|return|import|from|is|not|None|and|or|if|else|elif|class|for|in|True|False|with|as|raise|lambda|try|except|continue|pass)\b|\b(\d+)\b/g

/** Resaltado mínimo de Python para fragmentos (fuera de Monaco). Devuelve tokens, sin HTML. */
export function highlightPython(src: string): Token[] {
  const out: Token[] = []
  let last = 0
  for (const m of src.matchAll(RE)) {
    const i = m.index ?? 0
    if (i > last) out.push({ text: src.slice(last, i) })
    out.push({ text: m[0], cls: m[1] ? 'tok-s' : m[2] ? 'tok-c' : m[3] ? 'tok-k' : 'tok-n' })
    last = i + m[0].length
  }
  if (last < src.length) out.push({ text: src.slice(last) })
  return out
}
