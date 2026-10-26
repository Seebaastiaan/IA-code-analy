# Fórmula del score

Responsable: Diego Salinas (IA & Analizadores) · Sprint 6

El score oficial lo calcula **solo el backend** ([backend/app/analyses/scoring.py](../../backend/app/analyses/scoring.py)).
El frontend lo previsualiza con la misma fórmula al mover los pesos en Configuración
([frontend/src/shared/utils/score.ts](../../frontend/src/shared/utils/score.ts)), pero siempre muestra el valor
que devuelve la API.

## Categorías

Se calculan **al leer** el reporte, con los hallazgos **abiertos** y **no ignorados** (ni en rutas excluidas).
Por eso ignorar una regla, excluir una ruta, resolver un hallazgo en el editor o cambiar los pesos se refleja
de inmediato, sin re-analizar.

```
seg  = 100 − Σ penalización(seguridad)          penalización: alta 12 · media 6 · baja 2
prac = 100 − Σ penalización(buenas prácticas)   penalización: alta 6  · media 3 · baja 1
test = cobertura total − 5 × pruebas que fallan
```

Cada categoría se recorta al rango 0–100 y se redondea a un decimal.

- **Escala por tamaño:** si el proyecto tiene más de 1000 líneas de Python, la penalización de `seg` y `prac` se
  multiplica por `1000 / líneas`. 60 avisos en un proyecto de 10 000 líneas pesan lo mismo que 6 en uno de
  1000. Sin la escala, cualquier proyecto grande quedaba en 0.
- **Sin coverage elegido:** la cobertura no se midió y cuenta como 100; `test` solo descuenta las pruebas que fallan.

## Score global

```
global = (w_seg · seg + w_test · test + w_prac · prac) / (w_seg + w_test + w_prac)
```

Pesos por defecto: `seg 50 · test 30 · prac 20`. Si no suman 100 se normalizan; al menos uno debe ser mayor que 0.

## Configuración por proyecto

Desde la pantalla Configuración o el archivo `.ia_voy.toml` en la raíz del repositorio:

```toml
[pesos]
seguridad = 0.50
pruebas   = 0.30
practicas = 0.20

[umbrales]
score_minimo     = 70   # por debajo, el reporte y el tablero se marcan en rojo
cobertura_minima = 60   # archivos por debajo generan un hallazgo COV (en el siguiente análisis)

[reglas]
ignorar = ["B101"]

[rutas]
excluir = ["migrations/", "tests/fixtures/"]
```

- El archivo guarda fracciones (`0.50`); la app trabaja en porcentajes (`50`).
- Si un repositorio trae su `.ia_voy.toml`, se adopta en su **primer** análisis; después manda lo que se guarde
  desde la pantalla (que también escribe el archivo en el clon).

## Ejemplo

Reporte con 1 hallazgo de seguridad alta y 2 medias, 3 avisos de buenas prácticas bajos, cobertura 74 % y una
prueba que falla, en un proyecto de 800 líneas:

| Categoría | Cálculo | Valor |
|---|---|---|
| seg | 100 − (12 + 6 + 6) | 76.0 |
| prac | 100 − (1 + 1 + 1) | 97.0 |
| test | 74 − 5 | 69.0 |
| global | (50·76 + 30·69 + 20·97) / 100 | 78.1 |

Con pesos `40 / 40 / 20` el global sería `(40·76 + 40·69 + 20·97) / 100 = 77.4`.

## Verificación

- Backend: `tests/test_scoring.py` (escala por tamaño) y `tests/test_config_proyecto.py` (pesos e ignoradas
  aplicados al instante).
- Frontend: `tests/unit/score.test.ts` (misma fórmula, normalización y pesos en 0).
- Criterio del sprint: el score del frontend coincide con el de la API.
