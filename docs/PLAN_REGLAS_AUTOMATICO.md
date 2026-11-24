# Reglas de negocio automáticas: el programa trabaja por el equipo

Estado: en implementación (rama `sprint-9`). Continúa a [PROPUESTA_REGLAS_VERIFICABLES.md](PROPUESTA_REGLAS_VERIFICABLES.md).

## Problema

Hoy el módulo exige conocer el `reglas_negocio.toml`, aprobar regla por regla y pulsar cada paso técnico (arnés, humo,
pruebas, prueba de fuerza). Casi nadie sabrá qué poner en cada campo. Y aunque lo haga, no hay forma de saber si el
programa realmente detecta que el código sigue (o no) cada regla.

## Principio

**El programa trabaja por el equipo, no el equipo para el programa.** El TOML es un formato interno. La persona solo
ve lenguaje normal, y el programa **pregunta únicamente lo que no puede decidir solo**: de 40 reglas, «34 ya están
comprobadas y 6 necesitan una decisión tuya».

## La experiencia

1. Pone la URL del repo (y el documento de requisitos si el repo no lo trae) y pulsa **Analizar**.
2. El programa encuentra el documento, saca las reglas y arma arnés, pruebas y prueba de fuerza sin pasos manuales.
3. Lee un resultado en frases normales: 🟢 se cumple (con qué se comprobó), 🔴 no se cumple (qué caso falla y dónde,
   con «Corregir con IA»), 🟡 necesita una decisión.

El TOML, la plantilla, la regex y la matriz manual quedan en «Avanzado» (cerrado por defecto).

## Solo pregunta en 3 casos

1. **El documento es ambiguo** («¿el límite incluye el valor exacto?»): pregunta de sí o no, la respuesta se guarda.
2. **El código y el documento se contradicen**: «¿cuál es correcto?» (el documento manda → el código tiene un error;
   el código manda → hay que corregir el documento).
3. **No pudo comprobar** algo: lo dice en una frase y cómo resolverlo.

## Confianza automática (aprobación por el programa)

Una regla se aprueba sola solo si se cumplen **todas**:

- su cita textual existe en el documento (verificado por programa);
- no tiene dudas abiertas;
- dos pasadas independientes coinciden (la IA escribe la prueba desde la regla; otra consulta revisa el código sin ver
  esa prueba);
- la prueba toca el código de la regla (cobertura por prueba y mapa de endpoints);
- al inyectar una violación, la prueba la detecta (prueba de fuerza).

La prueba de fuerza solo se mide a las pruebas que **pasan** (dice si una prueba que pasa es floja). Una prueba que
**falla** se aprueba sola cuando la lectura independiente del código también dice que la regla no está o está solo en
parte: son dos comprobaciones que no se ven entre sí y señalan el mismo problema. Sin esto, ninguna regla rota llegaba
sola al reporte (medido con `inventario-demo`: las 5 reglas rotas quedaban «sin verificar»). Medición:
`backend/scripts/medir_preparar.py`.

Si falla una, la regla queda «a revisar» (casos 1, 2 o 3). Se marca **«aprobada por el programa»** y se puede revertir
en un clic. Las casillas «sé que se cumple / se viola» quedan como **casos de control opcionales** para medir al
programa (panel de concordancia: «acertó 11 de 12 reglas que conocían»).

## Pasos (cada uno ya sirve solo)

| # | Paso | Estado |
|---|---|---|
| 1 | Botón **Preparar todo**: encadena aprobar reglas → arnés → humo → pruebas → corrida → prueba de fuerza → segunda opinión sin pasos manuales | hecho: corre en el servidor (`app/projects/preparar.py`), sigue aunque se cierre la pestaña y se detiene al terminar el paso en curso. Si la prueba y la lectura del código no coinciden, la escribe una vez más, la corre y la mide antes de decidir (la IA no escribe igual cada vez). Las pruebas flojas (pasan, pero no notan algún cambio a propósito en el código de la regla) se reescriben mostrándole a la IA esos cambios. Las pruebas aprobadas que usan rutas que el código ya no tiene salen como «prueba rota» en el análisis y se escriben de nuevo |
| 2 | Aprobación automática por las condiciones de arriba y filtro «Necesitan mi decisión» | parcial: aprueba reglas sin dudas, el arnés y las pruebas fuertes y filtra por decisión; la marca «aprobada por el programa» ya está (`aprobada_por = "programa"` en el TOML, chip en la tabla y «Revertir a borrador» en un clic). Lo que no aprueba solo sale en «Esperan tu revisión» con el motivo, la recomendación y «Aprobar» en un clic |
| 3 | Cita textual verificada contra el documento y revisión independiente del código | hecho: la IA cita cada regla y el programa la busca en el documento (Word y PDF con texto; sin acentos ni signos, tolera un par de palabras distintas); sin cita o sin encontrarla, la regla queda con una duda y no se aprueba sola. «Preparar todo» hace una segunda lectura del código sin ver la prueba y la contrasta con el resultado (coincide / discrepa); solo se aprueban solas las pruebas fuertes que coinciden. La IA también avisa de frases del documento que parecen reglas y no extrajo (se comprueba que existan). Límite: un PDF escaneado (sin texto) queda «sin comprobar» |
| 4 | Casos 1 y 2 como preguntas de sí o no con memoria de respuestas | hecho: el caso 1 (documento ambiguo) está hecho: cada duda se contesta con Sí o No, la respuesta se anota en la descripción de la regla y se guarda en la memoria del proyecto (`business_rule_answers`); una importación nueva con la misma pregunta (redacción parecida, misma regla) se contesta sola. El caso 2 se resolvió con una regla simple: **el documento manda**. Una regla que el código viola muestra «El documento manda: el código tiene que seguir a la regla» y «Corregir con IA» (`POST …/reglas/pruebas/{id}/corregir`): la IA propone el cambio mínimo en el código —donde el análisis halló el patrón prohibido o donde la evidencia dice que está implementada—, nunca en la regla ni en su prueba, y se ve como diff en el editor sin guardar nada. Si el documento está mal, se corrige la regla (tabla de aprobación) y se vuelve a analizar |
| 5 | Pantalla de resultado con semáforo en lenguaje normal; TOML en «Avanzado»; «escribe una regla con tus palabras» | hecho: la vista Reglas del reporte resume («34 de 40 reglas se cumplen · 2 no se cumplen · 4 necesitan una decisión») y dice por regla 🟢/🔴/🟡 con qué se comprobó o qué caso falla y dónde; en Configuración el archivo `.toml` queda en «Avanzado» (cerrado, se abre solo si hay un error) y las reglas importadas se guardan con un botón visible; «Escribe una regla con tus palabras» la redacta la IA y entra en borrador. «Corregir con IA» está en cada regla roja (ver paso 4) y la plantilla y la ayuda de regex quedaron dentro de «Avanzado» |
| 6 | Casos de control (esperado) y panel de concordancia; confianza por regla | hecho: en Configuración, «¿Se le puede creer al programa?» deja marcar «sé que se cumple / se viola» en las reglas que se conocen (opcional, no cambia resultados) y compara con el último análisis: «Acertó 11 de 12 reglas que conocías». Cada regla muestra con qué solidez se comprobó (alta: pruebas y patrón; media: pruebas; baja: patrón). La confianza sale del nivel de verificación y la ajusta la prueba de fuerza de su prueba (fuerte sube un escalón; débil la deja como mucho en baja). La segunda opinión también cuenta: si coincide sube un escalón y si discrepa queda como mucho en baja. El reporte avisa de las reglas que se cumplían en el análisis anterior y ahora no |
| 7 | Caja negra con docker-compose y base de datos real | después |

## Límites que no desaparecen

Las pruebas comprueban ejemplos, no todos los casos; es evidencia, no demostración. Por eso la aprobación automática
exige todas las condiciones juntas y siempre es reversible.
