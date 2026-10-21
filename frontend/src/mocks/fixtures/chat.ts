import type { ChatResponse } from '@/features/assistant/types'

const MODEL = 'Gemini 2.5 Flash'

/** Respuestas de ejemplo por palabra clave. El backend real usa RAG (embeddings de Gemini en SQLite + Gemini/Groq). */
const ANSWERS: { k: RegExp; r: Omit<ChatResponse, 'model'> }[] = [
  {
    k: /auth|secret|clave|b105|jwt/i,
    r: {
      content:
        'El hallazgo **B105** en `auth.py:15` indica que `SECRET_KEY` está escrita en el código. Cualquiera con acceso al repositorio podría firmar tokens válidos.\n\nRecomendación: leerla con `os.environ["SECRET_KEY"]` y rotar la clave actual. Hay una corrección automática disponible.',
      sources: [{ file: 'auth.py', line: 15 }, { file: 'auth.py', line: 16 }],
      action: { finding_id: 1, label: 'Aplicar fix' },
    },
  },
  {
    k: /sql|inyecc|b608|api\.py/i,
    r: {
      content:
        "En `api.py:17` la consulta se construye concatenando el parámetro `cliente`, que viene de la URL. Un valor como `' OR 1=1 --` devolvería todos los pagos.\n\nUsa un marcador `?` y pasa el valor como parámetro de `execute`.",
      sources: [{ file: 'api.py', line: 17 }, { file: 'api.py', line: 18 }],
      action: { finding_id: 2, label: 'Aplicar fix' },
    },
  },
  {
    k: /cobertura|coverage|prueba|test/i,
    r: {
      content:
        'Los archivos con menor cobertura son:\n• `pagos/reembolsos.py` — 31 %\n• `pagos/procesador.py` — 69 %\n\nAdemás `test_crear_pago_invalido` falla porque espera 400 y la API responde 422. Empezaría por reembolsos: maneja dinero y casi no tiene pruebas.',
      sources: [{ file: 'pagos/reembolsos.py', line: 1 }, { file: 'tests/test_api.py', line: 13 }],
    },
  },
  {
    k: /procesar|complej|radon|lote/i,
    r: {
      content:
        '`procesar_lote()` tiene complejidad 24 (grado D): mezcla validación, agrupación por moneda y cobro en un solo bloque con muchos `if` anidados.\n\nPropuesta: extraer `validar_pago()`, `agrupar_por_moneda()` y `cobrar_grupo()`. Cada una quedaría por debajo de 8.',
      sources: [{ file: 'pagos/procesador.py', line: 20 }],
    },
  },
]

export function answer(message: string): ChatResponse {
  const hit = ANSWERS.find((a) => a.k.test(message))
  if (hit) return { ...hit.r, model: MODEL }
  return {
    content:
      'Estas respuestas son de ejemplo (modo mock). En la versión real, IA voy busca los fragmentos más relevantes del repositorio (embeddings de Gemini), arma el prompt con ellos y responde con Gemini (o Groq si se agota la cuota), citando siempre archivo y línea.',
    sources: [{ file: 'README.md', line: 1 }],
    model: MODEL,
  }
}

