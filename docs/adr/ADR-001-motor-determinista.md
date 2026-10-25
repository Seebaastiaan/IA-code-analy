# ADR-001 · El código determinista detecta; la IA solo explica

- **Estado:** aceptada (Sprint 4, 20 oct 2026)
- **Responsable:** Uriel Castorela (Equipo 3 · IA & Analizadores)

## Contexto

En el Sprint 3 el diagnóstico de un archivo se pedía directamente a la IA. La medición de estabilidad
(Diego Salinas) mostró que el mismo archivo daba resultados distintos en cada corrida, sin líneas exactas
y con un consumo alto de tokens. Con eso no se puede calcular un score reproducible.

## Decisión

1. Los hallazgos y el score los produce código determinista: Ruff, Radon, Bandit, pip-audit, pytest y
   coverage, con salida JSON estable. El equipo solo normaliza y puntúa.
2. La IA se limita a explicar y responder (asistente RAG, Sprint 7).
3. Los analizadores que ejecutan código del repo corren en un **entorno aislado** (`uv venv` en un
   sandbox WSL2 o Docker). El Sprint 4 entrega la base de ese camino: el análisis **clona el repo y
   crea el entorno aislado**, y cada análisis queda guardado en el historial del repositorio.

## Consecuencias

- Se retira el endpoint de diagnóstico por IA del Sprint 3.
- El pipeline del Sprint 4 tiene 2 pasos reales (clonar, crear entorno). Instalar dependencias y
  los analizadores se agregan en el Sprint 5 sobre el mismo job, sin cambiar el contrato del WebSocket.
- Sin sandbox (`SANDBOX=off`) el entorno se crea en el backend con `python -m venv`, sin ejecutar
  nada del repo analizado.
