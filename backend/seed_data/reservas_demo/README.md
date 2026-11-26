# Reservas Sereno

API de reservas de un centro de bienestar en Flask + SQLAlchemy + SQLite: servicios, profesionales, citas, anticipos,
cancelaciones con reembolso, correos al cliente, recordatorios, bloqueo de cuenta y permisos por rol.

## Contenido

| Ruta | Qué es |
|---|---|
| `reservas/` | La API (`crear_app` en `app.py`). La hora sale de `reloj.ahora()` y los correos de `correo.enviar()` |
| `reservas/web/` | La interfaz web (HTML, CSS y JavaScript sin compilar), en `/ui`: reservar, mis citas, agenda, servicios y anticipos |
| `reservas/datos_demo.py` | Datos de ejemplo opcionales (servicios, profesionales, 4 cuentas y 2 citas) |
| `docs/Requisitos.pdf` | Documento de requisitos del sistema |

## Correrlo

```bash
pip install -r requirements.txt
flask --app "reservas.app:crear_app()" crear-admin admin@sereno.example una-clave-larga
flask --app "reservas.app:crear_app()" run --debug
```

Sin `SMTP_HOST` los correos solo se escriben en el log.

### Con interfaz

```bash
python -m reservas.datos_demo          # opcional: servicios, profesionales y 4 cuentas (clave demo-clave-1234)
RESERVAS_DEMO=1 flask --app "reservas.app:crear_app()" run --debug
# abre http://localhost:5000 y entra con admin@sereno.example, recepcion@sereno.example, ana@sereno.example o luis@sereno.example
```

Un cliente nuevo se registra desde la pantalla de entrada. Con `RESERVAS_DEMO=1` la sección «Correos (demo)» muestra los
que la app envió (confirmación, cancelación y recordatorio).
