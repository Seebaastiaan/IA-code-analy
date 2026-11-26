# Revisión de usabilidad: reglas de negocio automáticas

Fecha: 2026-11-22. Método: recorrido de las pantallas en Chrome (escritorio 1280 px y celular 390 px) con el backend simulado, 16 capturas, y
lectura con la lista de sospechas de la conversación anterior. **No hubo una persona usándolo**: esto es una revisión de experto, no una
prueba con usuarios. Las capturas completas (`fullPage`) muestran la barra lateral encima del contenido; es un efecto de la captura, no un fallo.

Pantallas revisadas: Nuevo análisis · Configuración → Reglas (vacía, tras importar, con la tabla y una duda, durante «Preparar todo») ·
Reporte → Reglas (semáforo y regla incumplida abierta).

## Lo que funciona

- El **semáforo** del reporte se lee solo: «2 de 5 reglas se cumplen · 2 no se cumplen · 1 necesita una decisión» y una frase por regla.
- La caja roja **«El documento manda»** con su botón explica por qué y qué va a pasar.
- El aviso **«Las reglas nuevas todavía no están guardadas»** con su botón evita perder lo importado.
- El filtro **«Necesitan mi decisión»** y los **Sí / No** de las dudas reducen el trabajo a decisiones concretas.

## Problemas, de más a menos grave

### Alta

1. **Celular: el reporte se corta por la derecha.** En Reporte → Reglas, al abrir una regla, el título, la caja «El documento manda» y el texto de
   la regla quedan cortados (se lee «…no puede altera», «…el código tiene que seguir»). Es un desbordamiento real de la tabla en pantallas
   angostas (`RulesTab.tsx`), no una cuestión de gusto.
2. **El panel «Cómo se verifican» describe otro programa.** Son 6 pasos manuales con jerga («@pytest.mark.regla("RN-###")», «arnés», «prueba de
   humo», «el paso 10») y dicen que se hagan a mano cosas que «Preparar todo» ya hace. En celular cae al final de la página. Debería decir 3 cosas:
   importa el documento, contesta las dudas, pulsa «Preparar todo».
3. **No hay un camino único.** Configuración → Reglas apila 8 tarjetas (origen, editor, regla con tus palabras, Preparar todo, tabla, control,
   arnés, pruebas). «Preparar todo» aparece **antes** de la tabla de aprobación y de guardar. «Mapa y arnés de pruebas» (con su propio
   botón «Proponer con IA») y «Pruebas de las reglas» compiten con «Preparar todo» aunque hacen lo mismo en versión manual.
4. **Lo primero que se lee es jerga.** «Contenido de reglas_negocio.toml», «Sin reglas · El repositorio no tiene reglas_negocio.toml» y el
   subtítulo «La fuente oficial es reglas_negocio.toml» en una pantalla pensada para quien no conoce el archivo.

### Media

5. **Cuatro entradas para lo mismo:** «Sacar reglas de Requerimientos.pdf», la zona de arrastre, «Cargar reglas» y «Descargar plantilla» (en
   Nuevo análisis) y «Avanzado». No queda claro cuál usar primero.
6. **Las dudas se leen como un error.** El encabezado va en rojo («Dudas abiertas: contesta Sí o No…»), la pregunta en letra pequeña y tres
   botones (Sí, No, «Resuelta») pegados. «Resuelta» confunde con Sí/No: cierra sin guardar respuesta.
7. **Los títulos de las reglas salen cortados** en la tabla de aprobación («Solo un agente de soporte pu…») y hay que abrir cada fila para leer
   la regla. Las etiquetas (severidad, «1 duda», «Borrador») compiten por el mismo espacio.
8. **«Preparar todo» no dice cuánto tarda ni qué hace.** Los pasos usan nombres técnicos («Comprobar que el entorno arranca», «Leer el código sin
   ver la prueba…»), no hay estimación (puede tardar varios minutos) y no se explica qué pasa si Gemini se satura.
9. **El panel «¿Se le puede creer al programa?» aparece demasiado pronto.** Antes de cualquier análisis muestra tres selectores «No sé» y
   «Sin comprobar» sin explicar el punto amarillo. Aporta valor solo después del primer análisis.
10. **Frase repetida en el reporte:** la frase del semáforo sale bajo el título y otra vez, igual, en el detalle abierto.

### Baja

11. El aviso flotante («Reglas guardadas…») puede tapar botones de la tabla un par de segundos (visto sobre «Resuelta»).
12. «Aún no cuentan en el score» (reporte) no dice cuándo sí cuentan ni cómo cambiarlo.
13. No se revisó lectura con teclado ni con lector de pantalla, ni el contraste en modo oscuro.

## Cambios propuestos (orden sugerido)

1. Arreglar el desbordamiento del reporte en celular (problema 1).
2. Reescribir «Cómo se verifican» a 3 pasos y sin jerga; subirlo arriba del contenido (problemas 2 y 4).
3. Reorganizar Configuración → Reglas en un solo camino: **1 Importar → 2 Dudas y aprobación → 3 Preparar todo → 4 Resultado**, y llevar «Mapa
   y arnés», «Pruebas de las reglas» y el panel de control a un bloque «Avanzado» cerrado (problemas 3 y 9).
4. Dejar una sola entrada para importar; plantilla y carga manual dentro de «Avanzado» (problema 5).
5. Dudas: pregunta en tamaño normal, encabezado neutro, solo Sí / No visibles y «Resuelta» en un menú; mostrar el título completo de la regla
   en la tabla (problemas 6 y 7).
6. «Preparar todo»: nombres de pasos en lenguaje normal, «puede tardar 3 a 8 minutos» y un mensaje claro si la IA se satura (problema 8).

## Estado de los cambios

Hechos (2026-11-22): 1 (desbordamiento en celular: tabla en bloque, texto que parte palabras), 2 y 4 (panel «Cómo funciona» de 4 pasos arriba, sin jerga;
subtítulo y encabezados sin «reglas_negocio.toml»), 3 y problema 9 (un solo camino: importar → dudas y aprobación → «Preparar todo»; escribir una
regla, arnés, pruebas una por una y casos de control quedan en «Herramientas avanzadas», cerrado). Los puntos 5 y 6 también están hechos (una sola entrada para importar,
dudas como preguntas con «Cerrar sin responder», título completo en la tabla, nombres claros y «de 3 a 8 minutos» en «Preparar todo»).

## Asistente por pasos (segunda ronda)

Configuración → Reglas ahora muestra **un paso a la vez** (Importar → Preguntas y aprobación → Preparar todo → Resultado). El programa marca el paso en
curso según el estado de las reglas (sin reglas, con borradores, todo aprobado), avanza solo cuando el proyecto avanza y una franja «Siguiente:» dice
qué hacer ahora con un botón que lleva al paso. Se puede saltar a cualquier paso; los pasos no se desmontan, así que lo escrito en el editor no se
pierde. «Preguntas para ti» junta las dudas de todas las reglas en borrador y las muestra una por una, con la frase del documento al lado y lo que cambia con el Sí y con el No
(cuando la duda trae «(Sí = …; No = …)», como los plazos ambiguos). Las preguntas abiertas se contestan escribiendo (el backend acepta texto además de sí/no) y el importador ahora pide formular las dudas como sí/no con su efecto.
Los errores de la IA y del documento salen en palabras y con «Reintentar» cuando suelen pasar solos. Pendiente de la propuesta: ayuda «?» junto a los términos y la comparación con el análisis anterior.

## Para validar de verdad

Esta revisión no sustituye una prueba con una persona que no conozca el proyecto: pedirle que importe un documento y llegue a ver un resultado sin
ayuda, mientras alguien anota dónde se detiene. Sin esa prueba, el orden de arriba es una hipótesis.
