# Resultado esperado · Reservas demo

Segunda prueba de aceptación de [PROPUESTA_REGLAS_VERIFICABLES.md](../../../../docs/PROPUESTA_REGLAS_VERIFICABLES.md)
(§11.1): un servicio que atiende clientes, con hora controlada, correos y un documento que **se contradice**.
**No se lo enseñes a la IA**: es contra lo que se compara lo que ella propone.

## 1. Veredicto por regla

Con [reglas_negocio.toml](reglas_negocio.toml) cargado en la app y las pruebas de `tests/reglas/` corriendo en el
sandbox: **11 cumple · 4 no cumple · 0 pruebas que fallan al preparar**.

| Regla | Qué dice | Esperado | Error sembrado |
|---|---|---|---|
| RN-001 | Un profesional sin citas empalmadas | **no cumple** | Solo rechaza la misma hora de inicio (`Cita.inicio == inicio`, [citas.py:58](../reservas/citas.py#L58)); 10:00–11:00 y 10:30–11:30 pasan. La de los clientes (RN-002) sí revisa el empalme |
| RN-002 | Un cliente sin citas empalmadas | cumple | — |
| RN-003 | Horario de atención completo | cumple | — |
| RN-004 | 2 horas de anticipación | cumple | — |
| RN-005 | Máximo 3 citas activas | cumple | — |
| RN-006 | Anticipo del 30 % | cumple | — |
| RN-007 | Cancelar con ≥ 24 h reembolsa todo | **no cumple** | Compara con `>` ([citas.py:87](../reservas/citas.py#L87)): con 24 h exactas no reembolsa. Entre 24 y 48 h sí reembolsa todo y sin comisión (la resolución de las contradicciones se cumple) |
| RN-008 | Con < 24 h se retiene el anticipo | cumple | — |
| RN-009 | Premium: sin cargo hasta 12 h antes | cumple | El mismo `>` afecta a las 12 h exactas, pero las pruebas no usan ese límite |
| RN-010 | Correo de confirmación | cumple | — |
| RN-011 | Correo de cancelación con reembolso | cumple | — |
| RN-012 | Recordatorio único | cumple | — |
| RN-013 | Un cliente solo ve sus citas | **no cumple** | `GET /citas/<id>` no revisa el dueño ([app.py:190](../reservas/app.py#L190)); cancelar y la lista sí |
| RN-014 | Bloqueo tras 3 intentos fallidos | **no cumple** | `intentos_fallidos > INTENTOS_MAXIMOS` ([auth.py:29](../reservas/auth.py#L29)): bloquea en el 4.º intento, y tras 3 fallos se entra con la clave correcta |
| RN-015 | Permisos por rol | cumple | 24 celdas (8 acciones × 3 roles) |

Lo comprueba [backend/tests/test_demos_reglas.py](../../../tests/test_demos_reglas.py)
(`uv run --with sqlalchemy --with flask pytest tests/test_demos_reglas.py`).

## 2. Lo que debe proponer el importador

Desde [docs/Requisitos.pdf](../docs/Requisitos.pdf), que genera
[generar_requisitos_reservas.py](../../generar_requisitos_reservas.py):

- **17 reglas**: las 15 de `reglas_negocio.toml` más las 2 de finanzas (§7.1 cargo del 50 % con menos de 48 h; §7.2
  comisión del 10 %), que el equipo descarta al resolver las contradicciones.
- **§3.1 y §6.1 en una sola regla** (dicen lo mismo con otras palabras). Si salen dos, basta con que la validación avise
  que se parecen; no cuenta como contradicción.
- **1 regla de proceso** (§9.2, la recepción llama a quien no asistió): fuera del código.
- **Nada** de §1, §2, §7.3 ni §9.1 (objetivo, alcance, medio de pago, tecnología y disponibilidad).

## 3. Contradicciones

El archivo importado **no debe ser válido** hasta que el equipo deje una regla de cada par (o borre el comentario
`# CONTRADICCIÓN` si decide que no se contradicen).

| # | Pares que debe marcar | Por qué chocan | Resolución del equipo |
|---|---|---|---|
| 1 | §4.2 ↔ §7.1 | Entre 24 y 48 h, §4.2 reembolsa todo y §7.1 cobra 50 % | Gana §4.2 (RN-007) |
| 1b | §4.3 ↔ §7.1 | Con menos de 24 h, §4.3 retiene todo y §7.1 cobra 50 % | Gana §4.3 (RN-008) |
| 2 | §4.2 ↔ §7.2 | §4.2 reembolsa el 100 %, §7.2 descuenta 10 % | Gana §4.2: sin comisión (RN-007) |

Meta: se marcan **las contradicciones 1 y 2** (1b cuenta a favor, no en contra).

**No debe marcar** §4.4 contra §4.2 o §4.3: lo de los premium es una excepción para otro tipo de cliente (RN-009). Si la
marca, es un falso positivo.

## 4. Dudas sembradas

| # | Sección | Qué es ambiguo | Resolución |
|---|---|---|---|
| 1 | §3.4 | ¿Qué es una cita «activa»? ¿Cuentan las canceladas o las que ya pasaron? | Solo futuras y confirmadas (RN-005) |
| 2 | §4.1 | No dice cómo se redondea el 30 % | 2 decimales, a la mitad hacia arriba (RN-006) |
| 3 | §5.3 | «Un día antes»: ¿24 h antes o el día anterior a cierta hora? | Cuando faltan 24 h o menos (RN-012) |

Meta: al menos 2 de 3. Las contradicciones no cuentan como dudas.
