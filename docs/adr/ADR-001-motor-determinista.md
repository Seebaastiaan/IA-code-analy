# ADR-001 · El código determinista detecta y puntúa; la IA solo explica y responde

- Estado: aceptada
- Fecha: 20 de octubre de 2026 (Sprint 4)
- Responsable: Uriel Castorela (IA & Analizadores)

## Contexto

En el Sprint 3 el diagnóstico de un archivo se pidió directamente a la API de IA (`POST /api/diagnostico`).
La medición de estabilidad ([docs/ia/estabilidad-diagnostico.md](../ia/estabilidad-diagnostico.md)) y la
retrospectiva del sprint mostraron que:

- El mismo archivo daba resultados distintos en cada corrida: cambiaban los hallazgos y el score.
- Las líneas citadas no siempre eran exactas.
- Cada diagnóstico consumía muchos tokens (todo el archivo en el prompt), y un repositorio completo no cabe.

Un score que cambia sin que cambie el código no sirve para comparar un análisis contra el anterior ni para
un Quality Gate.

## Decisión

1. **Quién detecta y puntúa**: herramientas maduras con salida JSON estable, ejecutadas sobre el clon:
   - Seguridad: **Bandit** y **pip-audit**.
   - Pruebas: **pytest** y **coverage**.
   - Buenas prácticas: **Ruff** y **Radon**.

   El equipo solo normaliza su salida al contrato `FindingInput` ([docs/qa/parsing.md](../qa/parsing.md)) y
   calcula el score en el backend ([backend/app/analyses/scoring.py](../../backend/app/analyses/scoring.py)).
2. **Lenguaje analizado**: solo Python (los seis analizadores son de Python). Un repositorio sin `.py` se
   detiene con un mensaje claro y la lista de lenguajes que trae.
3. **Uso de la IA**: explicar y responder sobre el código con contexto real (asistente RAG con fuentes
   `archivo:línea`), nunca inventar números.
4. **Se retira el prototipo**: `app/diagnostico/`, el script de estabilidad y la pantalla de diagnóstico.
   El cliente de la IA (`app/assistant/llm.py`) se conserva para el asistente.

En este sprint corren de verdad Ruff, Bandit y Radon (solo leen el código). pip-audit, pytest y coverage
ejecutan el código del repo y necesitan un sandbox aislado (Sprint 5); mientras tanto se simulan a partir de
una semilla guardada con el reporte y sus hallazgos dicen "(simulado)".

## Score

```
seg  = 100 − Σ penalización de los hallazgos de seguridad abiertos   (alta 12 · media 6 · baja 2)
prac = 100 − Σ penalización de los hallazgos de buenas prácticas     (alta 6 · media 3 · baja 1)
test = cobertura total − 5 por cada prueba que falla
global = (50·seg + 30·test + 20·prac) / 100
```

En proyectos de más de 1000 líneas de Python la penalización se escala por cada 1000 líneas.

## Consecuencias

- El mismo commit produce siempre el mismo reporte: se puede comparar y fijar umbrales.
- El análisis no gasta cuota de la API de IA.
- La IA queda para el asistente, donde aporta valor sin afectar el score.
- Los casos de uso y RF del Documento Global que mencionaban el diagnóstico por IA, PDF/A, mutación, el
  Administrador o la contraseña local se actualizan con la tabla de la Planeación v3.
