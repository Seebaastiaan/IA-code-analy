> **Clave de respuestas de `seed_data/inventario_demo`: no se publica.** El repo `inventario-demo` es solo `seed_data/inventario_demo` (código,
> interfaz, documento de requisitos y README de producto), como cualquier otro repo. Aquí quedan las reglas resueltas, el
> veredicto esperado, las pruebas escritas a mano y su arnés; las pruebas del backend (`tests/demos.py`) combinan las dos
> carpetas y `scripts/medir_preparar.py` compara contra `referencia/ESPERADO.md`.

# Inventario de la cafetería (proyecto demo)

API de inventario en FastAPI + SQLAlchemy + SQLite: catálogo, lotes con PEPS, Kardex, recetas, mermas, ajustes,
costo promedio, impuestos, permisos por rol y bitácora.

Es el repo de aceptación de las reglas de negocio de IA voy
([docs/PROPUESTA_REGLAS_VERIFICABLES.md](../../../docs/PROPUESTA_REGLAS_VERIFICABLES.md) §11.1). Tiene **5 reglas
de negocio rotas a propósito**; cuáles son y el resultado esperado están en
[referencia/ESPERADO.md](referencia/ESPERADO.md). No lo uses como referencia de cómo hacer un inventario.

## Contenido

| Ruta | Qué es |
|---|---|
| `inventario/` | La API |
| `inventario/web/` | La interfaz web (HTML, CSS y JavaScript sin compilar), en `/ui`. Cada rol ve solo lo que la matriz de permisos del documento le deja hacer |
| `inventario/datos_demo.py` | Datos de ejemplo opcionales (4 productos con compras, una receta y una merma) |
| `docs/Requerimientos.docx` | Documento de requisitos del proyecto, con 15 reglas, 1 de proceso y 7 ambigüedades |
| `tests/reglas/` | Pruebas de las 18 reglas, escritas a mano, con `@pytest.mark.regla("RN-###")`. `conftest.py` es el arnés (fixtures `como`, `crear_producto`, `comprar`, `vender`) |
| `referencia/reglas_negocio.toml` | Las 18 reglas como las aprobaría el equipo. Fuera de la raíz a propósito, para que IA voy ofrezca sacarlas del documento |
| `referencia/ESPERADO.md` | Veredicto esperado por regla, errores sembrados y dudas del documento |

## Correrlo

```bash
pip install -r requirements.txt pytest
python -m pytest                       # 77 pruebas: 7 fallan a propósito (5 reglas)
uvicorn inventario.main:app --reload   # imprime un token por rol al crear la base
```

### Con interfaz

```bash
python -m inventario.datos_demo        # opcional: catálogo de ejemplo
INVENTARIO_DEMO=1 uvicorn inventario.main:app --reload
# abre http://localhost:8000 y elige un rol (gerente, almacenista, cajero o barista)
```

Sin `INVENTARIO_DEMO=1` la pantalla de entrada pide el token de un usuario. La interfaz sigue lo que dice el documento
(p. ej. el cajero no ve los precios editables), pero **los 5 errores sembrados siguen en la API**: el cajero no ve el
botón para cambiar precios, pero la API se lo permite (RN-017). La interfaz no los esconde ni los arregla.

## Probarlo en IA voy

1. Sube esta carpeta a un repo propio de GitHub (es código del equipo, se puede publicar).
2. **Nuevo análisis** con su URL: el cuadro de reglas dice que no hay `reglas_negocio.toml` y ofrece
   **Sacar reglas de docs/Requerimientos.docx**. Compara lo que propone con
   [referencia/ESPERADO.md §2 y §3](referencia/ESPERADO.md).
3. Para ver el veredicto esperado sin pasar por la IA, carga `referencia/reglas_negocio.toml` en
   **Configuración → Reglas de negocio** y analiza con `SANDBOX=wsl` o `docker`: deben salir 13 cumple y 5 no
   cumple.
4. Para probar las pruebas generadas (fase 4), analiza una rama sin `tests/reglas/`: así no hay pruebas del repo
   que ganen a las de la app.
