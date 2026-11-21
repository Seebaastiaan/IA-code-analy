# Resultado esperado · Inventario demo

Prueba de aceptación de [PROPUESTA_REGLAS_VERIFICABLES.md](../../../../docs/PROPUESTA_REGLAS_VERIFICABLES.md)
(§2 y §11.1). **No se lo enseñes a la IA**: es contra lo que se compara lo que ella propone.

## 1. Veredicto por regla

Con [reglas_negocio.toml](reglas_negocio.toml) cargado en la app y las pruebas de `tests/reglas/` corriendo en el
sandbox: **13 cumple · 5 no cumple · 0 pruebas que fallan al preparar**.

| Regla | Qué dice | Esperado | Error sembrado |
|---|---|---|---|
| RN-001 | Un producto con historial pasa a Inactivo | **no cumple** | `eliminar` borra siempre: `db.delete(producto)` ([rutas_productos.py:89](../inventario/rutas_productos.py#L89)), y la cascada se lleva el Kardex |
| RN-002 | SKU único | cumple | — |
| RN-003 | Código de barras único | cumple | — |
| RN-004 | Nombre interno único (sin mayúsculas ni espacios) | cumple | — |
| RN-005 | Unidad base bloqueada con movimientos | cumple | — |
| RN-006 | Stock nunca negativo | **no cumple** | La venta de un producto de reventa no revisa existencias ([servicios.py:157](../inventario/servicios.py#L157)); `descontar` deja el resto en negativo. Las mermas y ajustes sí revisan |
| RN-007 | El stock solo cambia con un movimiento | cumple | — |
| RN-008 | PEPS por fecha de entrada | cumple | — |
| RN-009 | Alerta al llegar al mínimo (≤) | cumple | — |
| RN-010 | Recetas descuentan insumos | cumple | — |
| RN-011 | Conversión de unidad de compra a base | cumple | — |
| RN-012 | Mermas sin ingreso | cumple | — |
| RN-013 | Precio de venta > 0 | cumple | — |
| RN-014 | Precio menor al costo: se guarda con aviso | cumple | — |
| RN-015 | Costo promedio ponderado | **no cumple** | Promedio simple de los dos costos, no ponderado por cantidad ([servicios.py:129](../inventario/servicios.py#L129)): 10 u a $10 + 30 u a $20 da $15.00 en vez de $17.50 |
| RN-016 | Precio base e impuestos separados | cumple | — |
| RN-017 | Permisos por rol | **no cumple** | `PRECIOS = ("gerente", "cajero")` ([rutas_productos.py:18](../inventario/rutas_productos.py#L18)): el cajero cambia precios y costos. Fallan 2 de las 44 celdas de la matriz |
| RN-018 | Bitácora con valor anterior y nuevo | **no cumple** | En `editar`, el valor anterior se lee después del `setattr` ([rutas_productos.py:81](../inventario/rutas_productos.py#L81)): queda igual al nuevo. El ajuste manual sí lo guarda bien |

Lo comprueba [backend/tests/test_demos_reglas.py](../../../tests/test_demos_reglas.py)
(`uv run --with sqlalchemy --with flask pytest tests/test_demos_reglas.py`).

## 2. Lo que debe proponer el importador

Desde [docs/Requerimientos.docx](../docs/Requerimientos.docx), que genera
[generar_requerimientos_inventario.py](../../generar_requerimientos_inventario.py):

- **18 reglas atómicas** que equivalen a las de `reglas_negocio.toml` (§4.2 se separa en 3 y §4.5 en 2).
- **1 regla de proceso** (§9.2, «el gerente firma cada lunes el reporte de mermas»): fuera del código. No está en el
  TOML v1 porque ese formato no tiene `tipo = "proceso"`.
- **Nada** de §1, §2, §3, §5.3 ni §9.1 (objetivo, alcance, glosario, tipos de movimiento, tecnología). El tiempo de
  respuesta de §9.1 es un requisito técnico, no una regla, y además quedaría fuera del código.

## 3. Las 7 dudas sembradas

Cada una está en el documento a propósito. Las resoluciones son las del equipo y están en la `descripcion` de cada
regla del TOML («Duda resuelta: …»).

| # | Sección | Qué es ambiguo | Resolución |
|---|---|---|---|
| 1 | §4.3 | Solo habla de productos **con** historial: ¿uno sin historial se puede borrar físicamente? | Sí (RN-001) |
| 2 | §4.2 | ¿«Café molido» y «café  Molido» son el mismo nombre? | Sí: sin mayúsculas ni espacios repetidos (RN-004) |
| 3 | §5.4 | Dice PEPS (por **entrada**) pero también «primero salga lo que primero caduca» (FEFO) | PEPS por fecha de entrada (RN-008) |
| 4 | §5.5 | ¿«Cruzar» el mínimo es `<` o `≤`? ¿Por qué medio llega la alerta? | `≤`; en `GET /alertas` (RN-009) |
| 5 | §4.5 | «Alertar y/o bloquear» | Alertar (RN-014) |
| 6 | §7.1 | No dice decimales ni redondeo del costo | 2 decimales, a la mitad hacia arriba (RN-015) |
| 7 | §8.1 | La matriz de permisos está incompleta (¿quién cambia precios, elimina, ajusta?) | Matriz de RN-017 y [test_permisos.py](../tests/reglas/test_permisos.py) |

Meta: el importador detecta **al menos 5 de las 7**. Una duda extra razonable (p. ej., §4.6 no da las tasas de IVA
e IEPS, o qué pasa si falta un insumo al vender una bebida) no cuenta en contra.
