# Reservas Sereno (proyecto demo)

API de reservas de un centro de bienestar en Flask + SQLAlchemy + SQLite: servicios, profesionales, citas, anticipos,
cancelaciones con reembolso, correos al cliente, recordatorios, bloqueo de cuenta y permisos por rol.

Es el segundo repo de aceptación de las reglas de negocio de IA voy
([docs/PROPUESTA_REGLAS_VERIFICABLES.md](../../../docs/PROPUESTA_REGLAS_VERIFICABLES.md) §11.1): un servicio que
atiende clientes, cuyas reglas dependen de la hora y de correos, y cuyo documento de requisitos **se contradice**.
Tiene **4 reglas rotas a propósito**; cuáles son y el resultado esperado están en
[referencia/ESPERADO.md](referencia/ESPERADO.md). No lo uses como referencia de cómo hacer un sistema de reservas.

## Contenido

| Ruta | Qué es |
|---|---|
| `reservas/` | La API (`crear_app` en `app.py`). La hora sale de `reloj.ahora()` y los correos de `correo.enviar()` |
| `docs/Requisitos.pdf` | Documento de requisitos: 2 contradicciones, 1 contradicción falsa (una excepción), 1 regla repetida, 3 dudas y 1 regla de proceso |
| `tests/reglas/` | Pruebas de las 15 reglas, escritas a mano. `conftest.py` es el arnés: `reloj` (hora fija), `buzon` (correos enviados), `como(rol)`, `crear_cliente`, `cita`, `reservar` |
| `referencia/reglas_negocio.toml` | Las 15 reglas con las contradicciones y dudas resueltas. Fuera de la raíz a propósito |
| `referencia/ESPERADO.md` | Veredicto esperado, errores sembrados, contradicciones y dudas del documento |

## Correrlo

```bash
pip install -r requirements.txt pytest
python -m pytest                       # 56 pruebas: 4 fallan a propósito (4 reglas)
flask --app "reservas.app:crear_app()" crear-admin admin@sereno.example una-clave-larga
flask --app "reservas.app:crear_app()" run --debug
```

Sin `SMTP_HOST` los correos solo se escriben en el log.

## Probarlo en IA voy

1. Sube esta carpeta a un repo propio de GitHub.
2. **Nuevo análisis** con su URL → **Sacar reglas de docs/Requisitos.pdf**. El aviso debe decir que el documento se
   contradice y el editor no debe dejar usar las reglas hasta resolverlo. Compara con
   [referencia/ESPERADO.md §2–§4](referencia/ESPERADO.md).
3. Para ver el veredicto esperado sin pasar por la IA, carga `referencia/reglas_negocio.toml` en
   **Configuración → Reglas de negocio** y analiza con `SANDBOX=wsl` o `docker`: 11 cumple y 4 no cumple.
