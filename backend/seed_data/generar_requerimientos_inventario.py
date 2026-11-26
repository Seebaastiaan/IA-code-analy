"""
Genera seed_data/inventario_demo/docs/Requerimientos.docx (docs/PROPUESTA_REGLAS_VERIFICABLES.md §11.1).

    python seed_data/generar_requerimientos_inventario.py

El texto vive aquí y no en el repo demo, para que el demo tenga un solo documento de requisitos (el .docx) y para
que este script no se analice como parte del proyecto. Sin dependencias: el .docx se arma con zipfile, y la salida
es la misma en cada corrida (fechas fijas dentro del zip).

El documento mezcla reglas con secciones que no lo son (objetivo, alcance, glosario, requisitos técnicos) y trae 7
ambigüedades a propósito, marcadas abajo con «DUDA n». Las resoluciones están en
inventario_demo/referencia/reglas_negocio.toml y la lista en inventario_demo/referencia/ESPERADO.md.
"""

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

SALIDA = Path(__file__).resolve().parent / "inventario_demo" / "docs" / "Requerimientos.docx"
FECHA_ZIP = (2026, 11, 21, 0, 0, 0)

# (estilo, texto) · estilo: titulo | h1 | h2 | p | vineta | tabla (texto = lista de filas)
CONTENIDO: list[tuple[str, object]] = [
    ("titulo", "Documento de requerimientos · Sistema de inventario"),
    ("p", "Cafetería La Molienda · Versión 1.2 · Equipo de producto"),
    ("tabla", [
        ["Versión", "Fecha", "Cambios"],
        ["1.0", "02/09/2026", "Primera versión (catálogo y existencias)"],
        ["1.1", "30/09/2026", "Recetas, mermas y costos"],
        ["1.2", "28/10/2026", "Permisos por rol y bitácora"],
    ]),

    ("h1", "1. Objetivo"),
    ("p", "Contar con un sistema que controle el inventario de las tres sucursales de la cafetería: el catálogo de "
          "productos, las existencias por lote, las ventas en caja, las mermas y los costos, de forma que el gerente "
          "sepa en todo momento cuánto hay, cuánto cuesta y quién movió qué."),

    ("h1", "2. Alcance"),
    ("vineta", "Incluye: catálogo, compras a proveedores, ventas de mostrador, recetas de bebidas, mermas, ajustes por conteo físico y reportes de costo."),
    ("vineta", "No incluye: facturación electrónica, nómina, programa de lealtad ni pedidos en línea."),
    ("vineta", "Se entrega como una API que usarán la caja (tableta) y el panel administrativo (web)."),

    ("h1", "3. Glosario"),
    ("tabla", [
        ["Término", "Significado"],
        ["SKU", "Clave interna del producto (p. ej. CAF-001)"],
        ["Kardex", "Registro de cada entrada y salida de un producto, con su saldo"],
        ["Lote", "Conjunto de piezas de una misma compra, con su fecha de entrada y su caducidad"],
        ["Insumo", "Producto que no se vende solo y se usa en recetas (leche, café en grano)"],
        ["Producto compuesto", "Producto que se prepara con una receta (un latte)"],
        ["Merma", "Producto que se pierde: caduca, se derrama o se rompe"],
    ]),

    ("h1", "4. Catálogo de productos"),
    ("h2", "4.1 Datos de cada producto"),
    ("p", "Cada producto tiene SKU, código de barras, nombre interno, tipo (reventa, compuesto o insumo), unidad de "
          "medida base, unidad de compra con su factor de conversión, precio de venta, impuestos, costo unitario, "
          "stock actual y stock mínimo."),
    ("h2", "4.2 Unicidad"),
    # DUDA 2: no dice si el nombre se compara sin mayúsculas ni espacios
    ("p", "El SKU, el código de barras y el nombre interno son únicos: el sistema no debe permitir dos productos con "
          "el mismo valor en cualquiera de los tres campos."),
    ("h2", "4.3 Baja de productos"),
    # DUDA 1: no dice qué pasa con un producto sin historial
    ("p", "Los productos que ya tienen historial (compras, ventas o mermas) no se eliminan físicamente de la base de "
          "datos. En su lugar pasan a estado «Inactivo»: dejan de aparecer en la caja pero su historial se conserva "
          "para los reportes."),
    ("h2", "4.4 Unidad de medida base"),
    ("p", "La unidad de medida base de un producto (pieza, gramo o mililitro) no se puede modificar una vez que el "
          "producto tiene movimientos de inventario, porque los saldos anteriores dejarían de tener sentido."),
    ("h2", "4.5 Precios"),
    # DUDA 5: «alerta y/o bloqueo»
    ("p", "El precio de venta siempre debe ser mayor a cero. Si al capturar o modificar un precio este resulta menor "
          "al costo unitario del producto, el sistema deberá alertar y/o bloquear la operación."),
    ("h2", "4.6 Impuestos"),
    ("p", "El catálogo maneja por separado el precio base y los impuestos aplicables (IVA e IEPS) con las tasas que "
          "correspondan a cada producto; el precio base nunca incluye impuestos."),

    ("h1", "5. Existencias y Kardex"),
    ("h2", "5.1 Existencias no negativas"),
    ("p", "El stock físico de un producto nunca puede ser menor a 0. La caja no debe permitir vender un producto sin "
          "existencias suficientes."),
    ("h2", "5.2 Movimientos auditados"),
    ("p", "El campo stock_actual no se edita directamente. Todo cambio de existencias debe registrarse como un "
          "movimiento del Kardex con el usuario, la fecha, la cantidad y el saldo resultante."),
    ("h2", "5.3 Tipos de movimiento"),
    ("p", "Los movimientos pueden ser: entrada por compra, salida por venta, consumo por receta, merma y ajuste por "
          "conteo físico."),
    ("h2", "5.4 Lotes y caducidades"),
    # DUDA 3: PEPS (por entrada) contra «lo que primero caduca» (FEFO)
    ("p", "Cada compra genera un lote con su fecha de entrada y, si aplica, su fecha de caducidad. Las salidas se "
          "toman de los lotes bajo el método PEPS (Primeras Entradas, Primeras Salidas), de modo que primero salga lo "
          "que primero caduca."),
    ("h2", "5.5 Stock mínimo"),
    # DUDA 4: «cruzar» (< o ≤) y por qué medio se avisa
    ("p", "Cuando las existencias de un producto crucen su stock mínimo, el sistema debe generar una alerta "
          "automática y marcar el producto en estado de reabastecimiento hasta que se registre una nueva compra."),
    ("h2", "5.6 Mermas y desperdicios"),
    ("p", "Las mermas tienen un flujo propio, independiente de las ventas: descuentan existencias pero no suman "
          "ingresos. Cada merma registra el motivo."),

    ("h1", "6. Recetas y unidades"),
    ("h2", "6.1 Productos de reventa y compuestos"),
    ("p", "Los productos de reventa (botellas de agua, galletas empacadas) se descuentan 1 a 1 al venderse. Los "
          "productos compuestos (bebidas preparadas) no tienen existencias propias: al venderse descuentan de cada "
          "insumo la cantidad que indica su receta, en proporción a lo vendido."),
    ("h2", "6.2 Conversión de unidades"),
    ("p", "Los insumos se compran en unidades de compra (cajas, costales, galones) y se consumen en unidades base "
          "(piezas, gramos, mililitros). El sistema convierte automáticamente con el factor de cada producto; por "
          "ejemplo, un costal de café equivale a 1000 g."),

    ("h1", "7. Costos"),
    ("h2", "7.1 Costo promedio"),
    # DUDA 6: no dice cuántos decimales ni cómo se redondea
    ("p", "Al registrar una compra con un precio de proveedor distinto, el costo unitario del producto se recalcula "
          "automáticamente con el método de costo promedio ponderado. El costo se expresa en pesos mexicanos."),

    ("h1", "8. Seguridad y auditoría"),
    ("h2", "8.1 Permisos por rol"),
    # DUDA 7: la matriz está incompleta (¿quién cambia precios, elimina, ajusta?)
    ("p", "Existen cuatro roles: cajero, barista, gerente y almacenista. Los cajeros y baristas solo pueden vender; "
          "los gerentes y almacenistas administran el inventario. Los permisos deben estar estrictamente separados."),
    ("h2", "8.2 Bitácora"),
    ("p", "Todo cambio en precios, costos o ajustes manuales de existencias debe quedar en una bitácora de auditoría "
          "con el usuario que lo hizo, la fecha, el valor anterior y el valor nuevo."),

    ("h1", "9. Otros requisitos"),
    ("h2", "9.1 Requisitos técnicos"),
    ("vineta", "La API se construye con FastAPI y SQLAlchemy; la base de datos de desarrollo es SQLite."),
    ("vineta", "Las pruebas automatizadas se escriben con pytest."),
    ("vineta", "Las consultas del catálogo deben responder en menos de 2 segundos en la red de la sucursal."),
    ("h2", "9.2 Operación"),
    ("p", "Cada lunes, el gerente de la sucursal revisa y firma el reporte de mermas de la semana anterior."),
]

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

CORE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>Requerimientos · Sistema de inventario</dc:title>
<dc:creator>Equipo de producto</dc:creator>
<dc:language>es-MX</dc:language>
<dcterms:created xsi:type="dcterms:W3CDTF">2026-10-28T00:00:00Z</dcterms:created>
</cp:coreProperties>"""


def _estilo(style_id: str, nombre: str, tam: int, negrita: bool = False, antes: int = 0, despues: int = 120, color: str = "000000") -> str:
    b = "<w:b/>" if negrita else ""
    return (f'<w:style w:type="paragraph" w:styleId="{style_id}"><w:name w:val="{nombre}"/><w:basedOn w:val="Normal"/>'
            f'<w:next w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="{antes}" w:after="{despues}"/></w:pPr>'
            f'<w:rPr>{b}<w:color w:val="{color}"/><w:sz w:val="{tam}"/></w:rPr></w:style>')


STYLES = (
    f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{W}">'
    '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>'
    '<w:sz w:val="22"/><w:lang w:val="es-MX"/></w:rPr></w:rPrDefault>'
    '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
    + _estilo("Title", "Title", 36, True, 0, 200, "1F3864")
    + _estilo("Heading1", "heading 1", 28, True, 360, 120, "1F3864")
    + _estilo("Heading2", "heading 2", 24, True, 240, 80, "2E74B5")
    + '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:tblPr><w:tblBorders>'
    + "".join(f'<w:{b} w:val="single" w:sz="4" w:space="0" w:color="999999"/>' for b in ("top", "left", "bottom", "right", "insideH", "insideV"))
    + '</w:tblBorders><w:tblCellMar><w:left w:w="100" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>'
    "</w:styles>"
)


def _run(texto: str, negrita: bool = False) -> str:
    rpr = "<w:rPr><w:b/></w:rPr>" if negrita else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(texto)}</w:t></w:r>'


def _parrafo(estilo: str, texto: str) -> str:
    if estilo == "vineta":
        return f'<w:p><w:pPr><w:ind w:left="360" w:hanging="240"/></w:pPr>{_run("• " + texto)}</w:p>'
    ppr = {"titulo": "Title", "h1": "Heading1", "h2": "Heading2"}.get(estilo)
    ppr_xml = f'<w:pPr><w:pStyle w:val="{ppr}"/></w:pPr>' if ppr else ""
    return f"<w:p>{ppr_xml}{_run(texto)}</w:p>"


def _tabla(filas: list[list[str]]) -> str:
    celdas = []
    for i, fila in enumerate(filas):
        sombra = '<w:shd w:val="clear" w:color="auto" w:fill="DEEAF6"/>' if i == 0 else ""
        celdas.append("<w:tr>" + "".join(f"<w:tc><w:tcPr>{sombra}</w:tcPr><w:p>{_run(c, i == 0)}</w:p></w:tc>" for c in fila) + "</w:tr>")
    return '<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="5000" w:type="pct"/></w:tblPr>' + "".join(celdas) + "</w:tbl><w:p/>"


def documento() -> str:
    cuerpo = "".join(_tabla(t) if estilo == "tabla" else _parrafo(estilo, t) for estilo, t in CONTENIDO)
    margen = '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body>{cuerpo}{margen}</w:body></w:document>'


def generar(salida: Path = SALIDA) -> Path:
    salida.parent.mkdir(parents=True, exist_ok=True)
    partes = {
        "[Content_Types].xml": CONTENT_TYPES, "_rels/.rels": RELS, "docProps/core.xml": CORE,
        "word/_rels/document.xml.rels": DOC_RELS, "word/styles.xml": STYLES, "word/document.xml": documento(),
    }
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, texto in partes.items():
            z.writestr(zipfile.ZipInfo(nombre, FECHA_ZIP), texto.encode("utf-8"), zipfile.ZIP_DEFLATED)
    return salida


if __name__ == "__main__":
    print(f"Escrito {generar()}")
