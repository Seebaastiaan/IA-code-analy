# Reporte final de calidad

Responsable: Evelyn Martínez (QA) · Sprint 10

Estado de calidad de IA voy v1.0 al cierre del proyecto.

## 1. Pruebas automatizadas

| Suite | Herramienta | Pruebas | Qué cubre |
|---|---|---|---|
| Backend | pytest | 195 | Auth y OAuth, GitHub, análisis y jobs (persistencia, varios workers, cancelar/reintentar), sandbox, analizadores y score, configuración y `.ia_voy.toml`, tablero, reportes y exportación, editor y correcciones, asistente (RAG, streaming, respaldo), comparativa, compartir, equipos |
| Frontend unitarias | Vitest | 22 | Estado del job, score y `.ia_voy.toml`, parches del editor, streaming del chat, sugerencias del asistente |
| Frontend e2e | Playwright | 8 | Los 5 flujos del spec, reintento de un análisis, equipo y validación de analizadores (backend simulado con MSW) |

Todas corren en el CI en cada Pull Request (`.github/workflows/ci.yml`): Ruff + pytest, oxlint + build + Vitest y
Playwright.

Las pruebas no hacen llamadas de red: GitHub, git y los modelos de IA se sustituyen por clientes falsos; Ruff,
Bandit y Radon corren de verdad sobre `seed_data/demo_repo`.

### Evolución por sprint

| Sprint | Backend | Unitarias | e2e |
|---|---|---|---|
| 2 | 4 | — | — |
| 3 | 16 | — | — |
| 4 | 101 | 12 | 7 |
| 5 | 112 | 12 | 7 |
| 6 | 123 | 12 | 7 |
| 7 | 162 | 22 | 7 |
| 8 | 179 | 22 | 8 |
| 9 | 195 | 22 | 8 |

## 2. Cobertura de requisitos

Ver [trazabilidad.md](trazabilidad.md): cada requisito con su módulo y sus pruebas.

## 3. Pruebas manuales

| Documento | Estado |
|---|---|
| [qa-manual.md](qa-manual.md): 18 casos contra el backend real | Llenar resultados |
| [sandbox-docker.md](sandbox-docker.md): 9 casos del sandbox Docker | Llenar resultados |
| [../ia/evaluacion.md](../ia/evaluacion.md): 12 preguntas al asistente | Llenar resultados |

## 4. Defectos

| Severidad | Abiertos | Cerrados |
|---|---|---|
| Crítico | | |
| Mayor | | |
| Menor | | |

Criterio de entrega: cero defectos críticos abiertos (Sprint 9, code freeze).

## 5. Riesgos y limitaciones aceptadas

| Riesgo | Mitigación |
|---|---|
| El sandbox WSL2 puede leer el disco de Windows | Usar `SANDBOX=docker` con repos ajenos ([sandbox-docker.md](sandbox-docker.md)) |
| SQLite con muchos usuarios a la vez | Suficiente para la escala del proyecto; PostgreSQL como trabajo futuro |
| El código analizado se envía al proveedor de IA al usar el asistente | Aviso en la guía de usuario; el análisis no envía nada |
| Cuota de la API de IA | Cadena de respaldo Gemini → Groq; el análisis no depende de la IA |
| El WebSocket del job no lleva token | El id del job es aleatorio (64 bits) y solo da lectura del progreso |

## 6. Cómo reproducir

```bash
cd backend && uv sync --extra dev && uv run pytest
cd frontend && npm ci && npm test && npm run test:e2e
```
