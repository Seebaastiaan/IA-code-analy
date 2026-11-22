# Inventario de la cafetería

API de inventario en FastAPI + SQLAlchemy + SQLite: catálogo, lotes con PEPS, Kardex, recetas, mermas, ajustes,
costo promedio, impuestos, permisos por rol y bitácora.

## Contenido

| Ruta | Qué es |
|---|---|
| `inventario/` | La API (`app` en `main.py`) |
| `inventario/web/` | La interfaz web (HTML, CSS y JavaScript sin compilar), en `/ui` |
| `inventario/datos_demo.py` | Datos de ejemplo opcionales (4 productos con compras, una receta y una merma) |
| `docs/Requerimientos.docx` | Documento de requisitos del sistema |

## Correrlo

```bash
pip install -r requirements.txt
uvicorn inventario.main:app --reload   # imprime un token por rol al crear la base
```

### Con interfaz

```bash
python -m inventario.datos_demo        # opcional: catálogo de ejemplo
INVENTARIO_DEMO=1 uvicorn inventario.main:app --reload
# abre http://localhost:8000 y elige un rol (gerente, almacenista, cajero o barista)
```

Sin `INVENTARIO_DEMO=1` la pantalla de entrada pide el token de un usuario.
