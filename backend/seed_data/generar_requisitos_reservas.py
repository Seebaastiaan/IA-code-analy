"""
Genera seed_data/reservas_demo/docs/Requisitos.pdf (docs/PROPUESTA_REGLAS_VERIFICABLES.md §11.1).

    python seed_data/generar_requisitos_reservas.py

Sin dependencias: un PDF de texto con las fuentes estándar (Helvetica), con la misma salida en cada corrida. El texto
vive aquí y no en el repo demo, para que el demo tenga un solo documento de requisitos.

El documento trae a propósito (marcado abajo):
- CONTRADICCIÓN 1: §4.2 reembolsa todo con 24 h; §7.1 cobra 50 % con menos de 48 h (también choca con §4.3).
- CONTRADICCIÓN 2: §4.2 reembolsa el 100 %; §7.2 descuenta 10 % de comisión en todo reembolso.
- FALSA CONTRADICCIÓN: §4.4 (premium, 12 h) es una excepción para otro tipo de cliente, no una contradicción.
- DUPLICADA: §3.1 y §6.1 dicen lo mismo con otras palabras.
- DUDA 1–3: §3.4 «activas», §4.1 redondeo, §5.3 «un día antes».
Las resoluciones están en reservas_demo/referencia/reglas_negocio.toml y la lista en reservas_demo/referencia/ESPERADO.md.
"""

import textwrap
from pathlib import Path

SALIDA = Path(__file__).resolve().parent / "reservas_demo" / "docs" / "Requisitos.pdf"

# (estilo, texto) · estilo: titulo | sub | h1 | h2 | p | vineta
CONTENIDO: list[tuple[str, str]] = [
    ("titulo", "Documento de requisitos · Sistema de reservas"),
    ("sub", "Centro de bienestar Sereno · Versión 2.0 · 14 de octubre de 2026"),
    ("sub", "Secciones 1 a 5 y 8: equipo de producto. Sección 6: recepción. Sección 7: finanzas."),

    ("h1", "1. Objetivo"),
    ("p", "Permitir que los clientes del centro reserven, paguen y cancelen sus citas de masaje, facial y fisioterapia "
          "desde la web, y que la recepción administre la agenda de los terapeutas sin hojas de cálculo."),

    ("h1", "2. Alcance"),
    ("vineta", "Incluye: catálogo de servicios, agenda de profesionales, reservas, anticipos, cancelaciones y avisos por correo."),
    ("vineta", "No incluye: facturación, nómina de los terapeutas ni la aplicación móvil (fase 2)."),

    ("h1", "3. Agenda"),
    ("h2", "3.1 Profesionales"),
    # DUPLICADA (con §6.1)
    ("p", "Un profesional no puede tener dos citas que se empalmen."),
    ("h2", "3.2 Clientes"),
    ("p", "Un cliente no puede tener dos citas confirmadas cuyo horario se empalme, aunque sean con profesionales distintos."),
    ("h2", "3.3 Horario y anticipación"),
    ("p", "El centro atiende de lunes a sábado de 9:00 a 20:00, y la cita completa debe quedar dentro de ese horario. "
          "Las reservas se hacen con al menos 2 horas de anticipación."),
    ("h2", "3.4 Límite de citas"),
    # DUDA 1: ¿qué es una cita «activa»? ¿cuentan las canceladas o las que ya pasaron?
    ("p", "Cada cliente puede tener como máximo tres citas activas."),

    ("h1", "4. Anticipo y cancelaciones"),
    ("h2", "4.1 Anticipo"),
    # DUDA 2: no dice cómo se redondea
    ("p", "Al reservar, el cliente paga un anticipo del 30 % del precio del servicio."),
    ("h2", "4.2 Cancelación a tiempo"),
    # CONTRADICCIÓN 1 y 2 (con §7.1 y §7.2)
    ("p", "Si el cliente cancela con al menos 24 horas de anticipación, se le reembolsa el 100 % del anticipo."),
    ("h2", "4.3 Cancelación tardía"),
    ("p", "Si cancela con menos de 24 horas de anticipación, el anticipo no se reembolsa. Una cita que ya comenzó no se "
          "puede cancelar."),
    ("h2", "4.4 Clientes premium"),
    # FALSA CONTRADICCIÓN: excepción para otro tipo de cliente
    ("p", "Los clientes premium pueden cancelar sin cargo hasta 12 horas antes de su cita."),

    ("h1", "5. Avisos al cliente"),
    ("h2", "5.1 Confirmación"),
    ("p", "Cada reserva confirmada envía un correo al cliente con el folio, el servicio, la fecha y la hora de la cita."),
    ("h2", "5.2 Cancelación"),
    ("p", "Cada cancelación envía un correo al cliente con el folio y el monto que se le reembolsa."),
    ("h2", "5.3 Recordatorio"),
    # DUDA 3: ¿24 horas antes o el día anterior a cierta hora?
    ("p", "Un día antes de la cita el sistema envía un recordatorio por correo. Cada cita recibe un solo recordatorio."),

    ("h1", "6. Operación de la agenda (recepción)"),
    ("h2", "6.1 Empalmes"),
    # DUPLICADA (con §3.1)
    ("p", "No se permite agendar a un terapeuta en dos citas cuyo horario se traslape, aunque sea parcialmente."),
    ("h2", "6.2 Reservas por teléfono"),
    ("p", "La recepción puede reservar a nombre de cualquier cliente que llame por teléfono."),

    ("h1", "7. Políticas de cobro (finanzas)"),
    ("h2", "7.1 Cargos por cancelación"),
    # CONTRADICCIÓN 1 (con §4.2 y §4.3)
    ("p", "Toda cancelación realizada con menos de 48 horas de anticipación genera un cargo del 50 % del anticipo."),
    ("h2", "7.2 Comisiones"),
    # CONTRADICCIÓN 2 (con §4.2)
    ("p", "En todo reembolso se descuenta una comisión bancaria del 10 % del monto reembolsado."),
    ("h2", "7.3 Medios de pago"),
    ("p", "Los anticipos se cobran con tarjeta a través de la pasarela del banco."),

    ("h1", "8. Seguridad y privacidad"),
    ("h2", "8.1 Privacidad"),
    ("p", "Un cliente solo puede ver y cancelar sus propias citas; las de otros clientes no deben mostrarse ni existir para él."),
    ("h2", "8.2 Acceso"),
    ("p", "Después de 3 intentos fallidos de inicio de sesión, la cuenta se bloquea durante 15 minutos."),
    ("h2", "8.3 Permisos"),
    ("p", "La administración da de alta servicios y profesionales, cambia precios y marca a los clientes premium. La "
          "recepción ve la agenda de los profesionales y envía los recordatorios. El cliente solo gestiona sus propias "
          "citas. El reporte de anticipos es exclusivo de la administración."),

    ("h1", "9. Otros requisitos"),
    ("h2", "9.1 Técnicos"),
    ("vineta", "La API se construye con Flask y SQLAlchemy; en desarrollo se usa SQLite."),
    ("vineta", "El sistema debe estar disponible el 99 % del horario de atención."),
    ("h2", "9.2 Operación"),
    ("p", "La recepción llama por teléfono a los clientes que no asistieron para ofrecerles una nueva cita."),
]

ANCHO, ALTO, MARGEN = 612, 792, 72
# Tamaño, interlineado, espacio antes, fuente (F1 normal, F2 negrita) y caracteres por línea (Helvetica ≈ 0.5 em)
ESTILOS = {
    "titulo": (17, 22, 0, "F2", 52), "sub": (10, 14, 2, "F1", 90), "h1": (13, 17, 16, "F2", 70),
    "h2": (11, 15, 8, "F2", 82), "p": (10, 14, 2, "F1", 92), "vineta": (10, 14, 2, "F1", 88),
}


def _texto_pdf(texto: str) -> str:
    # WinAnsiEncoding (cp1252): acentos, «», §, ·; se escapan los caracteres especiales de una cadena PDF
    crudo = texto.encode("cp1252")
    return "".join(f"\\{chr(b)}" if b in b"()\\" else chr(b) if 32 <= b < 127 else f"\\{b:03o}" for b in crudo)


def _paginas() -> list[str]:
    paginas: list[list[str]] = [[]]
    y = ALTO - MARGEN
    for estilo, texto in CONTENIDO:
        tam, salto, antes, fuente, ancho = ESTILOS[estilo]
        sangria = 14 if estilo == "vineta" else 0
        lineas = textwrap.wrap(texto, ancho)
        if estilo == "vineta":
            lineas = ["• " + lineas[0], *("  " + x for x in lineas[1:])]
        y -= antes
        # Un título no se queda solo al final de la página
        necesita = salto * (len(lineas) + (2 if estilo in ("h1", "h2") else 0))
        if y - necesita < MARGEN:
            paginas.append([])
            y = ALTO - MARGEN
        for linea in lineas:
            y -= salto
            paginas[-1].append(f"BT /{fuente} {tam} Tf {MARGEN + sangria} {y} Td ({_texto_pdf(linea)}) Tj ET")
    total = len(paginas)
    for n, comandos in enumerate(paginas, start=1):
        comandos.append(f"BT /F1 8 Tf {ANCHO - MARGEN - 60} 40 Td ({_texto_pdf(f'Página {n} de {total}')}) Tj ET")
    return ["\n".join(c) for c in paginas]


def documento() -> bytes:
    contenidos = _paginas()
    objetos: list[str] = []
    n_paginas = len(contenidos)
    # 1 catálogo · 2 páginas · 3 y 4 fuentes · 5 info · luego (página, contenido) por cada página
    ids_pagina = [6 + 2 * i for i in range(n_paginas)]
    objetos.append("<< /Type /Catalog /Pages 2 0 R >>")
    objetos.append(f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in ids_pagina)}] /Count {n_paginas} >>")
    objetos.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objetos.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    objetos.append("<< /Title (Requisitos - Sistema de reservas) /Author (Equipo de producto) /CreationDate (D:20261014000000Z) >>")
    for i, contenido in enumerate(contenidos):
        objetos.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ANCHO} {ALTO}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {ids_pagina[i] + 1} 0 R >>"
        )
        crudo = contenido.encode("latin-1")
        objetos.append(f"<< /Length {len(crudo)} >>\nstream\n{contenido}\nendstream")
    salida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    posiciones = []
    for n, obj in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += f"{n} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    salida += "".join(f"{p:010d} 00000 n \n" for p in posiciones).encode()
    salida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R /Info 5 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(salida)


def generar(salida: Path = SALIDA) -> Path:
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_bytes(documento())
    return salida


if __name__ == "__main__":
    print(f"Escrito {generar()}")
