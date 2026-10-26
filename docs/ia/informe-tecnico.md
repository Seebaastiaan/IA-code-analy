# Informe técnico de IA

Responsable: Uriel Castorela (IA & Analizadores) · Sprint 10

Cómo usa IA voy la inteligencia artificial, qué decidimos no delegarle y por qué. Detalle de implementación en
`docs/latex/` y en el código citado.

## 1. Evolución

| Sprint | Enfoque | Resultado |
|---|---|---|
| 2 | Diseño de prompts para diagnosticar un archivo (`docs/ia/prompts.md`, rama `sprint-2`) | Esquema JSON de hallazgos por categoría |
| 3 | La IA diagnostica un archivo de un repo clonado (`/api/diagnostico`) | Funciona, pero el mismo archivo da resultados distintos en cada corrida (`docs/ia/estabilidad-diagnostico.md`, rama `sprint-3`) |
| 4 | **ADR-001**: el código determinista detecta y puntúa; la IA solo explica y responde | Score reproducible; el análisis no gasta cuota |
| 7 | Asistente RAG sobre el código con streaming y fuentes `archivo:línea` | La IA responde con el código real como contexto |
| 8 | Set de evaluación y ajustes del prompt ([evaluacion.md](evaluacion.md), [ajustes-prompt.md](ajustes-prompt.md)) | Fuentes validadas, acciones solo con fix |
| 9 | Respaldo entre modelos: Gemini → Gemini alternos → Groq | El asistente sigue disponible ante 429/503 |

## 2. Motor determinista (detecta y puntúa)

Seis herramientas maduras con salida JSON estable, normalizadas a un contrato común
([catalogo-reglas.md](catalogo-reglas.md); el esquema de parsing original está en `docs/qa/parsing.md`, rama `sprint-2`):

| Categoría | Herramientas | Dónde corren |
|---|---|---|
| Seguridad | Bandit, pip-audit | Bandit en el backend; pip-audit en el sandbox |
| Pruebas | pytest, coverage | Sandbox WSL2/Docker (ADR-002) |
| Buenas prácticas | Ruff, Radon | Backend (solo leen el código) |

El score ([score.md](score.md)) se calcula en el backend al leer, con los hallazgos abiertos y la configuración del
proyecto (`.ia_voy.toml`). Mismo commit + misma configuración ⇒ mismo score.

## 3. Asistente RAG (explica y responde)

### Indexado ([backend/app/assistant/index.py](../../backend/app/assistant/index.py))

1. **Fragmentos** ([chunker.py](../../backend/app/assistant/chunker.py)): el `ast` de Python separa una función o clase
   por fragmento; clases grandes, por método; el resto de archivos de texto, en ventanas de 60 líneas con 10 de
   solapamiento.
2. **Embeddings**: `gemini-embedding-001` con 768 dimensiones, normalizados y guardados como `float32` en SQLite
   (`code_chunks`). No hace falta una base vectorial: la búsqueda es un producto punto con numpy.
3. **Incremental**: cada fragmento se identifica por el hash de su archivo y texto (sin números de línea). Antes de
   cada pregunta se vuelve a fragmentar (local) y solo se piden embeddings de lo nuevo; lo guardado en el editor se
   refleja sin re-indexar todo ni gastar cuota.

### Respuesta ([backend/app/assistant/router.py](../../backend/app/assistant/router.py))

1. Busca los 6 fragmentos más parecidos a la pregunta (y a la anterior, para preguntas de seguimiento).
2. Arma el contexto: resumen del reporte, hasta 20 hallazgos abiertos (sin reglas ignoradas), el hallazgo mencionado
   con ±12 líneas y los fragmentos con número de línea.
3. Pide a Gemini un JSON con esquema (`answer`, `sources`, `finding_id`), temperatura 0.2, `answer` primero para el
   streaming (SSE).
4. **Valida**: descarta las fuentes que no estaban en el contexto y solo ofrece "Aplicar corrección automática" si el
   hallazgo está abierto y tiene fix de Ruff.

### Respaldo ([backend/app/assistant/llm.py](../../backend/app/assistant/llm.py))

`GEMINI_MODEL` → `GEMINI_FALLBACK_MODELS` → Groq (Llama 3.3) solo ante 429 (cuota) o 503 (demanda), con un reintento
del mismo modelo ante 503. Si ya se mostró parte de una respuesta no se cambia de modelo (se mezclarían dos
respuestas). La pantalla indica qué modelo respondió.

## 4. Seguridad y privacidad

- Las claves viajan en cabeceras (`x-goog-api-key`, `Authorization`), nunca en la URL ni en el frontend.
- El prompt declara el código del repositorio como **datos**: ignora instrucciones escritas en comentarios o textos.
- El código del repositorio se envía a Google (y a Groq si actúa el respaldo) para responder: se avisa en la guía de
  usuario. El análisis y el score no envían nada a terceros.

## 5. Evaluación

Set de 12 preguntas sobre el repo de demostración ([evaluacion.md](evaluacion.md)) con criterios de corrección,
fuentes válidas, no inventar, acción correcta, formato y tiempo al primer texto. Las pruebas automáticas
(`backend/tests/test_assistant.py`, 28 casos) usan un modelo falso: cubren contexto, validación de fuentes,
acciones, historial, errores del proveedor, streaming y la cadena de respaldo sin red ni cuota.

## 6. Límites conocidos

- Contexto acotado (6 fragmentos + 20 hallazgos): preguntas que abarcan todo el repositorio reciben respuestas parciales.
- La búsqueda es semántica pura (sin BM25): nombres exactos poco descriptivos a veces no se encuentran.
- Groq no tiene embeddings: si Gemini no responde embeddings, el asistente contesta solo con el reporte.
- Los mensajes de Bandit y Ruff siguen en inglés en el reporte; el asistente los explica en español.

## 7. Trabajo futuro

- Búsqueda híbrida (BM25 + embeddings) y re-ranking.
- Explicaciones de hallazgos pre-generadas al terminar el análisis (opcional, por costo).
- Evaluación automática con un conjunto de respuestas de referencia.
