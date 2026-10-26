# Matriz de trazabilidad

Responsable: Luis Gabriel Manzano (QA) · Sprint 10

Cada funcionalidad del producto con su origen (pantalla o flujo de `docs/FRONTEND_SPEC.md`, decisión de la
Planeación v3), el sprint en que se entregó, el código que la implementa y las pruebas que la verifican. La columna
**RF / CU** se completa con los identificadores del Documento Global (actualizados en el Sprint 4 con la tabla de
decisiones de la Planeación v3).

## Funcionalidades

| # | Funcionalidad | Origen | RF / CU | Sprint | Backend | Frontend | Pruebas |
|---|---|---|---|---|---|---|---|
| 1 | Iniciar sesión con GitHub (OAuth, `state` de un solo uso, token cifrado) | Spec §5.1, §6.1, §6.10 | | 4 | `app/auth.py`, `app/github/` | `features/auth/` | `test_auth.py` (10), e2e (sesión automática con MSW) |
| 2 | Repos y ramas de la cuenta de GitHub (incluidos privados) | Spec §5.3, §6.10 | | 5 | `app/github/router.py` | `features/github/` | `test_github.py` (4) |
| 3 | Analizar un repositorio: clonado real y 11 pasos en vivo | Spec §5.3, §6.3, Flujo 1 | | 4 | `app/analysis/jobs.py`, `clone.py`, `router.py` | `features/analysis/` | `test_analysis.py` (22), `job.test.ts` (5), e2e 1 |
| 4 | Solo Python: repos sin `.py` se detienen con un mensaje claro | Planeación v3 §1 | | 4 | `app/analysis/languages.py` | `ReportHeader` | `test_languages.py` (4) |
| 5 | Motor determinista: Ruff, Bandit, Radon | ADR-001 | | 4 | `app/analyses/analyzers.py`, `app/analysis/pipeline.py` | — | `test_scoring.py`, `test_modules.py` |
| 6 | Sandbox: pip-audit, pytest y coverage reales (WSL2/Docker) | ADR-002 | | 5 | `app/analysis/sandbox.py` | Opción "Ejecutar en sandbox" | `test_sandbox.py` (12), `qa/sandbox-docker.md` |
| 7 | Analizadores elegibles (uno por categoría) | Spec §5.3 | | 5 | `app/analysis/router.py` | `AnalyzeForm` | `test_jobs.py` (5 de 10), e2e "analizador por categoría" |
| 8 | Score ponderado por categoría, escalado por tamaño | Spec §7.1, Planeación v3 §1 | | 4 / 6 | `app/analyses/scoring.py`, `views.py` | `shared/utils/score.ts` | `test_scoring.py` (4), `score.test.ts` (5), `ia/score.md` |
| 9 | Reporte: hallazgos, cobertura, complejidad, filtros | Spec §5.5, §6.4 | | 4 | `app/reports/router.py` | `features/report/` | `test_modules.py`, e2e 1 |
| 10 | Detalle del hallazgo con su código | Spec §5.6 | | 5 | `app/analyses/workspace.py` (fragmentos) | `features/findings/` | `test_modules.py::test_reporte`, e2e 2 y 4 |
| 11 | Re-analizar con los mismos analizadores | Spec §5.4 | | 5 | `app/analysis/router.py` | `useReanalyze` | `test_analysis.py`, `test_jobs.py` |
| 12 | Página de repositorios | Spec §5.4 | | 5 | `app/dashboard/router.py` | `features/repos/` | `test_modules.py::test_lista_de_repos_e_historial` |
| 13 | Configuración por proyecto y `.ia_voy.toml` | Spec §5.11, §6.8 | | 6 | `app/projects/`, `app/analyses/config_file.py` | `features/settings/` | `test_config_proyecto.py` (22), `score.test.ts`, e2e 5 |
| 14 | Ignorar una regla desde el hallazgo (score sin re-analizar) | Spec §5.6 | | 6 | `app/analyses/views.py` | `useIgnoreRule` | `test_config_proyecto.py::test_ignorar_regla_se_aplica_al_instante` |
| 15 | Tablero con tendencia y atención prioritaria | Spec §5.2, §6.2, Flujo 5 | | 6 | `app/dashboard/router.py` | `features/dashboard/` | `test_modules.py` (tablero), `test_analysis.py::test_tablero`, e2e 5 |
| 16 | Editor: leer, guardar con respaldo y re-analizar | Spec §5.8, §6.5, Flujo 2 | | 7 | `app/editor/router.py`, `workspace.py` | `features/editor/` | `test_modules.py` (editor), e2e 2 |
| 17 | Correcciones automáticas de Ruff (parches) | Spec §5.6, §5.8 | | 7 | `app/analyses/analyzers.py` (`fix_content`, `diff_patches`) | `useApplyFix`, `utils/patches.ts` | `test_modules.py` (diff ×7), `patches.test.ts` (6), e2e 2 |
| 18 | Archivos del repositorio (solo lectura) | Spec §5.4 | | 7 | `app/editor/router.py` (`tree`, `file`) | `RepoFilesPage` | `test_analysis.py::test_arbol_y_archivos_del_clon` |
| 19 | Asistente RAG con fuentes `archivo:línea` | Spec §5.9, §6.6, Flujo 4 | | 7 | `app/assistant/` | `features/assistant/` | `test_assistant.py` (28), `suggestions.test.ts` (3), e2e 4 |
| 20 | Respuesta en streaming (SSE) | Spec §6.6 | | 7 | `app/assistant/router.py` (`/chat/stream`) | `postStream`, `chat.api.ts` | `test_assistant.py` (streaming), `chatStream.test.ts` (3) |
| 21 | Respaldo de modelos Gemini → Groq | Planeación v3 §1 | | 9 | `app/assistant/llm.py` | `AssistantPage` | `test_assistant.py` (respaldo), `qa-manual.md` caso 12 |
| 22 | Equipos con invitación por enlace | Planeación v3 §1 (sustituye la matriz de permisos) | | 8 | `app/teams/` | `features/team/` | `test_teams.py` (9), e2e "equipo" |
| 23 | Compartir con enlace público (contraseña, expiración) | Spec §5.7, §5.12, §6.9, Flujo 3 | | 8 | `app/share/router.py` | `features/share/`, `features/public-report/` | `test_share.py` (12), e2e 3 |
| 24 | Exportar a JSON, HTML, Markdown y SARIF | Planeación v3 §1 (sustituye PDF/A) | | 8 | `app/reports/router.py` (`export`) | `ShareModal` | `test_modules.py::test_exportar` (4), `test_exportar_html_escapa` |
| 25 | Comparativa entre análisis (nuevos y resueltos) | Spec §5.10, §6.7, Flujo 5 | | 9 | `app/compare/router.py` | `features/compare/` | `test_compare.py` (14), e2e 5 |
| 26 | Cancelar y reintentar un análisis | Spec §5.3 | | 9 | `app/analysis/jobs.py` | `JobView` | `test_analysis.py::test_cancelar`, `test_jobs.py`, e2e 1b |
| 27 | Jobs persistentes y varios workers | Planeación v3 §1 | | 9 | `app/analysis/jobs.py`, tabla `jobs` | — | `test_jobs.py` (5 de persistencia) |
| 28 | Formato de errores `{error: {code, message}}` | Spec §6 | | 2 | `app/errors.py` | `shared/api/http.ts` | `test_auth.py::test_body_invalido_usa_formato_de_error` |
| 29 | Claves generadas y persistentes (`SECRET_KEY`, Fernet) | Planeación v3 §1 | | 2 | `app/config.py` | — | `test_config.py` (2) |

## Fuera de alcance (Planeación v3)

| Elemento de la Planeación v2 | Decisión |
|---|---|
| Reglas propias BP/SEG/PR | Sustituidas por Ruff, Bandit, Radon, pip-audit, pytest y coverage (ADR-001) |
| Mutación (mutmut) | Fuera de alcance: demasiado lenta dentro del sandbox |
| Boilerplates de prueba con IA (RF-20) | Fuera de alcance: la IA se limita al asistente |
| Administrador (CU-12) | Sustituido por la configuración por proyecto |
| PDF/A con WeasyPrint | Sustituido por la exportación (el HTML se imprime a PDF) |
| Usuario/contraseña local | Sustituido por el login con GitHub |

## Cómo mantenerla

Cada Pull Request que agregue una funcionalidad agrega su fila con el código y las pruebas. Una funcionalidad sin
prueba automática debe tener un caso en `docs/qa/qa-manual.md`.
