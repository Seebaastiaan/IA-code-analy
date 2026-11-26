# Primera corrida real: `reservas-demo` con Gemini y el sandbox

Fecha: 2026-11-22. Repo: `urielbatizzzzzzzz/reservas-demo` (público). Modelo: Gemini 3.5 Flash Lite. Sandbox: WSL. Verdad contra la que se compara:
`backend/seed_data/reservas_demo_clave/referencia/ESPERADO.md` (4 reglas rotas a propósito: empalme de profesionales, reembolso a las 24 h exactas,
cliente que ve la cita de otro y bloqueo tras 3 intentos).

## Qué se encontró y se corrigió

| Hallazgo | Medición | Corrección |
|---|---|---|
| La IA numeraba las reglas distinto de como quedan en la lista y marcaba el par de contradicciones equivocado (`RN-007`/`RN-015` en vez de `RN-007`/`RN-016`) | 1 de 1 corridas | Las contradicciones se resuelven por título |
| Con una sola consulta, las contradicciones salían en 3 de 5 corridas y la comisión del 10 % (§7.2) nunca | 5 corridas | Segunda consulta solo de contradicciones sobre la lista final numerada por el programa: 4 de 4 corridas con las dos contradicciones reales |
| Regla repetida (§3.1 y §6.1) sin unir; regla de proceso (§9.2) casi siempre omitida | 25 reglas en la 1.ª corrida; proceso en 1 de 5 | Prompt más explícito: 19 a 23 reglas y proceso en 4 de 4 |
| La memoria de respuestas casi no reconocía la misma duda: solo 1 de 6 pares de redacciones pasaba el parecido de texto | Gemini redacta distinto cada vez | Comparación por significado (embeddings: misma duda ≥ 0,92, distinta ≤ 0,82): 3 de 3 reimportaciones reconocieron las 2 dudas |
| «Corregir con IA» arregló `RN-007` pero quitó la excepción premium | 1 de 1 | Recibe las demás reglas y la orden de cambiar solo lo mínimo: `>` a `>=` en 3 de 3 intentos; `RN-001` bien en 3 de 3 |

## Resultados que quedan como están

- **Citas verificadas:** 100 % en todas las importaciones (el texto del PDF se leyó bien).
- **Importación:** 19 a 23 reglas por corrida (esperado: 17). Hay variación entre corridas; una vez marcó una contradicción falsa
  (recordatorio automático frente a permiso de la recepción).
- **Pruebas escritas por la IA:** 17 de 18 reglas (una sin prueba). Del primer reparto: 2 de las 4 reglas rotas salieron «no cumple»
  (reembolso, privacidad); 2 pasaron como «cumple» (empalme de profesionales y bloqueo): falsos negativos. Hubo 3 falsos positivos
  (límite de 3 citas, correo de cancelación con monto inventado, permisos).
- **La red de seguridad funcionó:** de las 5 pruebas que se aprobaron solas (prueba fuerte y lectura del código que coincide), las 5 eran
  de reglas que sí se cumplen. El falso negativo del empalme lo marcó la lectura independiente («discrepa»); el del bloqueo quedó sin
  aprobar porque su prueba era solo «parcial» (4 de 6 cambios detectados).
- **Reanálisis con esas pruebas:** el resultado cambia entre corridas de las mismas pruebas (p. ej. el empalme salió «cumple» y luego
  «no cumple»; el límite de 3 citas, al revés). Las pruebas de la IA no son deterministas ni totalmente aisladas: por eso nada se aprueba
  sin la prueba de fuerza y la lectura del código.
- **Panel de concordancia** (17 reglas marcadas con la verdad): acertó 12, falló 1 y 4 quedaron sin verificar.

## Lo que sigue pendiente

- Las pruebas generadas siguen produciendo falsos positivos y negativos: la aprobación automática es prudente, pero la mayoría de las
  reglas termina esperando una decisión de una persona.
- La corrida no cubrió `inventario-demo` ni el paso 7 (caja negra con docker-compose y base de datos real).
- Solo se midió con un modelo (Gemini 3.5 Flash Lite); con otro modelo cambiarán las cifras.

## Segunda ronda: mejorar las pruebas que escribe la IA

Se midió regenerando las pruebas de las 18 reglas aprobadas desde cero, corriéndolas en el sandbox y comparando con `ESPERADO.md`
(17 reglas con prueba; la de proceso queda fuera del código). Antes de esta ronda las pruebas de reglas del repo `tests/reglas/`
(escritas a mano con otra numeración) se quitaron del clon local: el importador numera distinto y se enlazaban a reglas que no eran.
Nota para el reanálisis de la primera ronda: sus cifras están contaminadas por ese cruce de números.

| Medición | Aciertos | Falsos positivos | Falsos negativos | Sin prueba o rota |
|---|---|---|---|---|
| Antes (1 corrida) | 12 | 3 | 2 | 1 |
| Con prompt y validadores (3 corridas) | 13 · 12 · 13 | 0 · 1 · 1 | 1 · 1 · 1 | 4 · 4 · 3 |
| Con insistencia, nombres y usuarios (3 corridas) | 13 · 15 · 15 | 1 · 1 · 2 | 2 · 0 · 0 | 2 · 2 · 1 |

Qué se cambió y por qué (cada punto sale de una prueba real que falló):

- **Aislar la regla.** La prueba del empalme de profesionales usaba el mismo cliente dos veces y el rechazo venía de la regla del
  cliente. El prompt pide aislarla y un validador rechaza dos variables con `como("mismo-rol")` (es el mismo usuario).
- **«¿Pasaría igual sin la regla?».** La prueba del bloqueo probaba un cuarto intento con clave incorrecta, que falla con o sin bloqueo.
  El prompt pide probar con una acción válida (clave correcta tras 3 fallos, y justo antes del límite).
- **Cifras y formatos.** Una prueba esperaba «30» en el correo y otra suponía el folio igual al id y la fecha en ISO. Un validador rechaza
  cifras que no están en la regla; el prompt pide usar los campos exactos de la respuesta y revisar asunto y cuerpo del correo.
- **Códigos de rechazo.** Se rechaza `in (400, 422)` sin 409 (la API respondía 409) y se explica que credenciales y bloqueos son 401 o 423.
- **Código vacío.** Con frecuencia Gemini decía «no implementada» con endpoints que sí existen y dejaba el código vacío (reglas sin
  prueba en 1 a 2 de cada 3 corridas). Ahora se le insiste una vez; en las 3 últimas corridas escribió 18 de 18.
- **Nombres corruptos.** Un nombre con una letra árabe (`reloj.ir_ا`) rompía la prueba; un validador lo detecta y se reintenta.

Lo que sigue fallando:

- **Recordatorio (RN-012):** falso positivo en 3 de 3 corridas. La prueba pone el reloj 25 h antes de la cita y el código avisa dentro de 24 h.
  Es más una duda del documento («un día antes») que un error de la IA: debería salir como duda a contestar.
- **Variación entre corridas:** falsos negativos del empalme y del bloqueo en 1 de 3 corridas cada uno; una prueba rota de vez en cuando.
- Solo se probó con un modelo y un repo.

## Tercera ronda: los plazos ambiguos se preguntan

El falso positivo del recordatorio (RN-012) era una ambigüedad del documento: «un día antes» puede ser 24 horas exactas o el día calendario
anterior. La IA a veces la preguntaba y a veces no, así que ahora el importador la detecta de forma determinista
(`reglas_importar.TIME_AMBIGUITIES`: «un día antes», «el día anterior», «la víspera», «al día siguiente», «una semana o un mes antes» y
«días hábiles») y agrega una duda de sí o no, salvo que la regla ya la tenga o sea de proceso. La respuesta queda en la descripción.

Comprobado con Gemini real: al reimportar el PDF, `RN-012` salió con la duda «¿«un día antes» significa exactamente 24 horas antes?».
Con la respuesta «Sí», la prueba regenerada puso el reloj a las 10:00 del día anterior (24 h exactas) y **pasó 3 de 3 veces**
(antes: falso positivo 3 de 3 con el reloj a las 9:00, 25 h antes).
