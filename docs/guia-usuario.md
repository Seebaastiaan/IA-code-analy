# Guía de usuario

Responsable: Karen Peña (Front-End & UX) · Sprint 10

IA voy analiza la calidad de proyectos **Python** en GitHub y da un score de 0 a 100 en tres categorías:
**seguridad**, **pruebas** y **buenas prácticas**.

## 1. Iniciar sesión

1. Abre la app y pulsa **Continuar con GitHub**.
2. Autoriza a IA voy (solo la primera vez). Pide acceso a tus repos para poder analizar también los privados.
3. Entras al **Tablero**. Tu primer inicio de sesión crea tu equipo personal ("Equipo de …").

IA voy nunca ve tu contraseña de GitHub; el permiso se puede revocar en GitHub → Settings → Applications.

## 2. Analizar un repositorio

1. **Nuevo análisis** (menú o botón del tablero).
2. Elige un repo de la lista **Repositorios de @tu-usuario** (o escribe la URL `https://github.com/equipo/proyecto`) y
   la **rama**.
3. Revisa los **analizadores** (al menos uno por categoría) y las opciones:
   - **Ejecutar en sandbox**: corre pip-audit, pytest y coverage aislados. Sin sandbox se simulan y lo verás como
     "(simulado)".
   - **Indexar para el asistente**: permite preguntarle a la IA sobre el código.
4. **Iniciar análisis**. Verás los 11 pasos y la terminal en vivo. Puedes seguir usando la app: el indicador del
   encabezado muestra el avance.
5. Al terminar, **Ver reporte**.

Si el análisis falla (rama inexistente, repo sin Python…) verás el motivo y podrás **Reintentar** o **Editar
parámetros**. También puedes **Cancelar** un análisis en curso.

> Solo se analiza Python. Un repositorio sin archivos `.py` se detiene con la lista de lenguajes que tiene.

## 3. Leer el reporte

- **Score global** y su variación contra el análisis anterior. Si está bajo el umbral del proyecto se marca en rojo.
- **Tarjetas por categoría**: haz clic para filtrar los hallazgos de esa categoría.
- Pestañas **Hallazgos**, **Cobertura** y **Complejidad**. Busca por archivo, regla o texto y filtra por severidad.
- Haz clic en un hallazgo para ver su **código**, **por qué importa** y **cómo corregirlo**.

| Severidad | Significado |
|---|---|
| Alta | Explotable o rompe el programa: corrígelo primero |
| Media | Riesgo real pero acotado |
| Baja | Estilo o mantenibilidad |

## 4. Corregir

- **Aplicar corrección automática** (hallazgos con la marca **Fix**, reglas de Ruff): abre el editor con el cambio
  propuesto en modo diff. Pulsa **Guardar**: el archivo se re-analiza y el score se actualiza al momento.
- **Abrir en editor**: edita a mano y guarda. Se guarda un respaldo de la versión anterior.
- **Ignorar la regla** en este proyecto: el hallazgo desaparece y el score se recalcula sin re-analizar.

## 5. Preguntar a la IA

**Asistente IA** (menú, botón **Preguntar** del reporte o **Preguntar a la IA** desde un hallazgo):

- Pregunta sobre el código ("¿Dónde se procesa el pago?") o sobre un hallazgo.
- La respuesta llega mientras se escribe e incluye **fuentes** `archivo:línea`: haz clic para abrirlas en el editor.
- Si la IA recomienda una corrección automática, aparece el botón para aplicarla.
- El encabezado del chat indica el modelo que respondió (si el principal está saturado responde uno de respaldo).

> Para responder, el código del repositorio se envía al proveedor de IA (Google Gemini; Groq como respaldo).

## 6. Tablero y comparativa

- El **Tablero** muestra el score del repo elegido, la tendencia de los últimos análisis (toca la leyenda para
  ocultar series) y los hallazgos que requieren atención.
- **Comparativa**: elige dos análisis (A y B) del mismo repo para ver los hallazgos **nuevos** y **resueltos** y la
  diferencia de score.

## 7. Configuración del proyecto

En **Configuración**:

- **Pesos** de cada categoría en el score global (se normalizan si no suman 100).
- **Umbrales**: score mínimo y cobertura mínima.
- **Reglas ignoradas** y **rutas excluidas**.

La vista previa muestra el `.ia_voy.toml` que se guarda en el repositorio. Si tu repo ya trae uno, se adopta en el
primer análisis.

## 8. Compartir y exportar

En el reporte, **Compartir**:

- Crea un **enlace público** de solo lectura, con contraseña opcional y expiración (1, 7, 30 días o nunca).
- Por defecto solo muestra los hallazgos de severidad alta y media, sin código; puedes incluir los fragmentos.
- **Exportar** a JSON, HTML (se imprime a PDF desde el navegador), Markdown o **SARIF** (lo leen GitHub y los IDE).

## 9. Equipo

En **Equipo** (quien administra):

- **Crear enlace de invitación** (válido 7 días, para varias personas).
- Renombrar el equipo, **ceder** la administración y **quitar** miembros.

Quien recibe el enlace ve el equipo y los repos que se descartarían (si ya existen en el equipo) antes de **Unirse**.
Al unirse, los repos, reportes y la configuración son compartidos por todo el equipo.

## 10. Preguntas frecuentes

| Pregunta | Respuesta |
|---|---|
| ¿Por qué cambió mi score sin re-analizar? | Ignoraste una regla, cambiaste los pesos, excluiste una ruta o corregiste algo en el editor |
| ¿Qué significa "(simulado)"? | Ese análisis corrió sin sandbox: pip-audit, pytest y coverage no se ejecutaron de verdad |
| No veo mis repos de GitHub | Pulsa **Volver a conectar GitHub** en Nuevo análisis (el permiso se revocó o venció) |
| El asistente dice "Sin configurar" | El servidor no tiene la clave de la API de IA |
