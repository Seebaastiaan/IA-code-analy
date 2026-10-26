# QA manual con backend real

Responsable: Marco Espino (IA & Analizadores) · Sprint 9

Las pruebas e2e (`frontend/tests/e2e`) usan el backend simulado (MSW) porque el login real pasa por GitHub.
Este recorrido valida los mismos flujos contra el **backend real**, con una cuenta de GitHub y el sandbox.

## Preparación

| Paso | Comando / acción |
|---|---|
| Backend | `cd backend && uv sync --extra dev && uv run uvicorn app.main:app --port 8000` con `.env` completo (OAuth, `GEMINI_API_KEY`, `SANDBOX=wsl`) |
| Frontend | `cd frontend && npm run dev` (`VITE_USE_MOCKS=false`) |
| Datos | Entrar una vez con GitHub y correr `uv run python -m app.seed --login <usuario>` |
| Repos de prueba | `seed_data/demo_repo` subido a un repo propio (puede ser privado) y un repo sin Python (p. ej. uno de JavaScript) |

## Casos

Marcar ✅ / ❌ y anotar el detalle de cada falla en la tabla de defectos.

| # | Flujo | Pasos | Resultado esperado | Resultado |
|---|---|---|---|---|
| 1 | Login | "Continuar con GitHub" → autorizar | Vuelve al tablero con nombre y avatar; `/api/auth/me` responde 200 | |
| 2 | Login cancelado | Cancelar en GitHub | "Cancelaste la autorización en GitHub." con botón para reintentar | |
| 3 | Analizar repo privado | Nuevo análisis → elegir el repo desde la lista de GitHub → rama | Terminal en vivo con 11 pasos; reporte con hallazgos reales | |
| 4 | Sandbox real | Analizar el demo con `SANDBOX=wsl` | pip-audit: 5 paquetes vulnerables; pytest: 2 passed; cobertura medida (sin "(simulado)") | |
| 5 | Repo sin Python | Analizar un repo de JavaScript | Se detiene en el paso 1: "El repositorio no tiene código Python" con sus lenguajes | |
| 6 | Rama inexistente | Analizar con rama `no-existe` | Error "La rama no existe"; Reintentar disponible | |
| 7 | Cancelar y reintentar | Iniciar un análisis → Cancelar → Reintentar | Estado "cancelado"; al reintentar termina y genera el reporte | |
| 8 | Corregir | Reporte → hallazgo F401 → Aplicar corrección → Guardar | El hallazgo pasa a resuelto y el score sube | |
| 9 | Ignorar regla | Hallazgo → Ignorar la regla | Desaparece del reporte; el score se recalcula sin re-analizar | |
| 10 | Configuración | Cambiar pesos → Guardar | Score del tablero con los pesos nuevos; `.ia_voy.toml` escrito en el clon | |
| 11 | Asistente | Preguntar "¿Dónde se procesa el pago?" | Respuesta en streaming con fuente `pagos/procesador.py:…`; clic abre el editor en esa línea | |
| 12 | Respaldo del modelo | Poner un `GEMINI_MODEL` inexistente con cuota agotada (o forzar 429) | Responde el modelo de respaldo y la pantalla lo indica | |
| 13 | Compartir | Compartir con contraseña → abrir en ventana privada | Pide contraseña; con la correcta muestra el reporte sin el menú de la app | |
| 14 | Exportar | Exportar a SARIF y HTML | Descarga `reporte-<id>.sarif.json` y `.html` válidos | |
| 15 | Equipo | Invitar → otra cuenta abre `/join/{code}` → Unirse | La segunda cuenta ve los repos del equipo | |
| 16 | Comparativa | Analizar → corregir → re-analizar → Comparativa | B tiene el hallazgo corregido en "Resueltos" | |
| 17 | Varios workers | `uvicorn app.main:app --workers 2` y repetir el caso 3 | El progreso en vivo funciona aunque el WebSocket caiga en otro worker | |
| 18 | Reinicio a mitad | Reiniciar el backend durante un análisis | El job queda "El análisis se interrumpió" y se puede reintentar | |

## Defectos encontrados

| # | Caso | Descripción | Severidad (crítico / mayor / menor) | Estado |
|---|---|---|---|---|
| | | | | |

Criterio de salida del Sprint 9: cero defectos críticos abiertos.
