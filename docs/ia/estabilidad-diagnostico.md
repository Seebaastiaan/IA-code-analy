# Medición de estabilidad del diagnóstico

Responsable: Diego Salinas (IA & Analizadores) · Sprint 3

## Pregunta

¿El diagnóstico con IA (`POST /api/diagnostico`) da el **mismo resultado** si se pide varias veces sobre el
**mismo archivo**? Si no, no sirve para calcular un score ni para comparar un análisis contra el anterior.

## Método

Script: [`backend/scripts/estabilidad_diagnostico.py`](../../backend/scripts/estabilidad_diagnostico.py).

1. Levantar el backend con `GEMINI_API_KEY`.
2. Correr el mismo archivo N veces (temperatura 0.2, el mismo prompt y el mismo commit):

   ```bash
   cd backend
   uv run python scripts/estabilidad_diagnostico.py --url https://github.com/<equipo>/<repo> --file <archivo.py> --runs 10
   ```

3. Comparar entre corridas:
   - **Score**: mínimo, máximo y desviación estándar.
   - **Hallazgos por corrida**: si el número cambia, el reporte cambia sin que cambie el código.
   - **Coincidencia de reglas** (índice de Jaccard entre cada par de corridas): 1.00 = siempre las mismas reglas.
   - **Coincidencia de regla + línea**: mide si las líneas citadas son las mismas.
   - **Tiempo por corrida** y tokens consumidos (panel de Google AI Studio).

## Criterio

Para usar el resultado como score oficial se pide, como mínimo:

| Métrica | Umbral |
|---|---|
| Desviación del score | 0 (el mismo archivo da el mismo número) |
| Coincidencia de regla + línea | ≥ 0.95 |

## Resultados

Llenar con la salida del script (una tabla por archivo medido):

| Archivo | Corridas | Score (mín · máx · desv.) | Hallazgos (mín · máx) | Jaccard reglas | Jaccard regla + línea | Tiempo medio |
|---|---|---|---|---|---|---|
| | | | | | | |

## Conclusión

Se presenta en la retrospectiva del Sprint 3 y abre el Sprint 4: si el diagnóstico no cumple el criterio, el
score no puede salir de la IA (ver la decisión del Sprint 4 en `docs/adr/`).
