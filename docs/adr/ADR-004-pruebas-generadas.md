# ADR-004 · La IA escribe las pruebas de las reglas de negocio; solo cuentan las aprobadas y el veredicto sale de ejecutarlas

- Estado: aceptada · implementada en Sprint 9 (fase 4 de [PROPUESTA_REGLAS_VERIFICABLES.md](../PROPUESTA_REGLAS_VERIFICABLES.md))
- Fecha: 21 de noviembre de 2026
- Relacionado: [ADR-001](ADR-001-motor-determinista.md) · [ADR-002](ADR-002-sandbox.md) · [ADR-003](ADR-003-reglas-de-negocio.md)

## Contexto

[ADR-003](ADR-003-reglas-de-negocio.md) dejó dos formas de verificar una regla:
- patrones (regex), que casi ninguna regla real admite;
- pruebas del equipo con `@pytest.mark.regla("RN-###")`, que casi nadie escribe.

Con un documento real (15 reglas de inventario) el resultado era 1 regla verificable y 14 «sin verificar».

Que la IA lea el código y diga «cumple» o «no cumple» contradice [ADR-001](ADR-001-motor-determinista.md): daría
resultados distintos en cada análisis y no deja evidencia que se pueda volver a correr.

## Decisión

1. **La IA escribe la prueba; la prueba decide.**
   - Con el arnés del proyecto aprobado (`tests/_ia_voy_reglas/conftest.py`, fase 3), Gemini escribe una prueba pytest
     por regla, a partir de:
     - la regla y la plantilla de su tipo;
     - el mapa del proyecto (`ast`, sin IA);
     - los esquemas y el código más parecido a la regla.
   - El veredicto sale de ejecutarla en el sandbox ([ADR-002](ADR-002-sandbox.md)).
2. **Solo cuentan las aprobadas.**
   - Una prueba generada entra como borrador.
   - Se corre una vez en el sandbox y el equipo la aprueba viendo el código, los supuestos de la IA y el resultado.
   - Aprobar exige que haya corrido con ese mismo código y que no esté rota.
   - Editarla, o que cambie la regla, invalida la aprobación.
   - El análisis **nunca** llama a la IA: corre las pruebas aprobadas guardadas.
3. **No se culpa al código por una prueba mala** (estados de la propuesta, §9).
   - El plugin `ia_voy_reglas` guarda el tipo de excepción de cada falla. Un `assert` (o `pytest.fail` /
     `pytest.raises`) que falla es **no cumple**; cualquier otra excepción (`preparar`, un fixture, un import, un
     `KeyError`) es **prueba rota** y no cuenta en contra.
   - **No implementada** se decide con el mapa, no con la opinión de la IA: la prueba declara qué endpoints usa y,
     si alguno no existe en el código, la regla queda no implementada.
   - Tipo `proceso` = **fuera del código**.
4. **Lo que se puede revisar sin ejecutar se revisa con `ast`.**
   - Errores:
     - el marcador de la regla en cada prueba;
     - pedir solo fixtures del arnés;
     - no usar nombres sin definir;
     - imports y llamadas permitidos;
     - no usar nombres que no existen en los módulos del proyecto.
   - Si hay errores, se le devuelven a la IA **una vez** para que corrija.
   - Las reparaciones mecánicas (`def_test_…`, imports olvidados de `pytest` o `Decimal`) se hacen sin IA.
5. **Las del repo tienen prioridad.**
   - Las pruebas de la app corren aparte (`tests/_ia_voy_reglas/`, con su propio `reglas_app.json`). No cuentan en las
     fallas ni en la cobertura del repo.
   - Para una regla que el repo ya prueba, se ignoran.
   - La app exporta un zip (reglas, arnés y pruebas aprobadas en `tests/reglas/`) para hacer commit; desde ese momento
     son pruebas del repo.

## Consecuencias

- Las reglas pasan de «sin verificar» a un veredicto con evidencia ejecutable.
- Con Gemini 3.5 Flash Lite, en los dos repos demo (§6.6 de la propuesta):
  - todas las reglas rotas a propósito salen «no cumple»;
  - ninguna regla que cumple sale «no cumple» con una prueba sin editar en el demo de reservas, y en inventario solo
    una prueba necesitó un cambio de un carácter antes de aprobarse.
- **Riesgo:** el equipo aprueba sin leer.
  - Mitigaciones: se muestran los supuestos y la primera corrida; una regla que sale «no cumple» avisa que se revise
    la prueba antes de aprobarla; una prueba rota no se puede aprobar.
  - Fase 5: la **prueba de fuerza** (mutación dirigida, sin IA) cambia a propósito las líneas de la regla y avisa si
    la prueba no lo nota («débil»). No bloquea la aprobación ni cambia el estado: es información para quien aprueba.
- Las pruebas de permisos salen de una **matriz que marca el equipo**, sin IA; lo que hace el código hoy se muestra
  como sugerencia, pero no se copia solo (el oráculo es la regla).
- La **evidencia de apoyo** (IA) dice dónde parece estar implementada la regla. Tampoco cambia el estado: solo ayuda a
  revisar la prueba y elige qué líneas muta la prueba de fuerza.
- En el sandbox **la red está bloqueada**: una prueba que intenta salir a internet queda rota (no se culpa al código).
- **Costo:** una llamada a Gemini por regla (dos si hay que corregir), solo al hacer clic.
- Las reglas todavía no entran al score (fase 6).
