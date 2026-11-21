/**
 * Repos CRUD de prueba (docs: README de cada uno) con su reglas_negocio.toml tal cual está en GitHub, para la
 * revisión de Nuevo análisis. Generado desde los repos: si cambian sus reglas, vuelve a copiarlas aquí.
 * biblioteca y cafetería traen un archivo válido; papelería trae 8 errores de formato a propósito.
 */

export interface CrudRepo {
  content: string
  /** Archivos del repo (para avisar `rutas` que no existen) */
  files: string[]
}

export const CRUD_REPOS: Record<string, CrudRepo> = {
  'urielbatizzzzzzzz/crud-biblioteca': {
    content: `# reglas_negocio.toml — reglas de negocio de la Biblioteca escolar (formato de IA VOY)
#
# Cada regla dice, en palabras de la biblioteca, qué debe pasar siempre. IA VOY la comprueba de una de dos formas:
#   - con una PRUEBA: tests/test_reglas.py tiene una prueba marcada @pytest.mark.regla("RN-00X") que simula el caso
#     del \`criterio\` (Dado… cuando… entonces…). Si la prueba pasa, la regla se cumple.
#   - con un PATRÓN: un texto que NO debe aparecer en el código (\`prohibido\`) o que SÍ debe aparecer (\`obligatorio\`).

[proyecto]
nombre  = "Biblioteca escolar"
version = "1.1"

[[regla]]
id          = "RN-001"
titulo      = "Un alumno tiene máximo 3 libros a la vez"
descripcion = "Para que alcancen los libros para todos, un alumno no puede llevarse un cuarto libro mientras tenga 3 sin devolver. Cuando devuelve uno, ya puede pedir otro."
severidad   = "alta"
historia    = "HU-02 Pedir un libro prestado"
responsable = "Bibliotecaria"
criterio    = "Dado que Ana tiene 3 libros sin devolver, cuando pide un cuarto libro, entonces el sistema se lo niega; cuando devuelve uno, ya puede pedir otro"
# Se verifica con la prueba test_alumno_no_pasa_de_tres_prestamos

[[regla]]
id          = "RN-002"
titulo      = "Un libro prestado no se le presta a otro alumno"
descripcion = "Si un libro ya está prestado, nadie más puede llevárselo hasta que lo devuelvan. Así el sistema nunca dice que un libro está disponible cuando no está en el estante."
severidad   = "alta"
historia    = "HU-03 Ver si un libro está disponible"
responsable = "Bibliotecaria"
criterio    = "Dado que Ana tiene «El Principito», cuando Luis lo pide, entonces se le niega; cuando Ana lo devuelve, Luis ya puede llevárselo"
# Se verifica con dos pruebas: el libro prestado se niega y el libro devuelto se vuelve a prestar

[[regla]]
id          = "RN-003"
titulo      = "Multa de $5 por cada día de retraso"
descripcion = "Un libro se presta por 14 días. Si se devuelve después, el alumno paga $5.00 por cada día de retraso; si se devuelve a tiempo, no paga nada."
severidad   = "media"
historia    = "HU-05 Cobrar multas"
responsable = "Dirección"
criterio    = "Dado un libro prestado el 1 de marzo, cuando se devuelve el 18 de marzo (3 días tarde), entonces la multa es de $15.00; si se devuelve el 15 de marzo, la multa es de $0.00"
# Se verifica con la prueba test_multa_por_dias_de_retraso

[[regla]]
id          = "RN-004"
titulo      = "No se borra del catálogo un libro que está prestado"
descripcion = "Un libro que alguien tiene en su casa no se puede eliminar del sistema: se perdería el registro de quién lo tiene y nunca se le pediría de regreso."
severidad   = "media"
historia    = "HU-04 Dar de baja un libro"
responsable = "Bibliotecaria"
criterio    = "Dado que Ana tiene «El Principito», cuando la bibliotecaria intenta borrarlo del catálogo, entonces el sistema no lo permite"
# Se verifica con la prueba test_no_se_elimina_libro_prestado

[[regla]]
id          = "RN-005"
titulo      = "Lo que se escribe en el buscador no puede alterar la base de datos"
descripcion = "El texto que un alumno escribe en el buscador de libros se trata solo como texto a buscar. Si se pegara tal cual dentro de la consulta, alguien podría escribir algo como ' OR 1=1 -- y ver o borrar datos."
severidad   = "alta"
rutas       = ["biblioteca/"]
# PATRÓN: en el código de la biblioteca no debe aparecer  execute(f"  , que es pegar el texto dentro de la consulta.
# La forma correcta es  execute("... LIKE ?", (f"%{texto}%",)) .
prohibido   = 'execute\\(f"'
responsable = "Equipo de desarrollo"
criterio    = "Dado que un alumno busca ' OR 1=1 --, cuando se hace la búsqueda, entonces no aparece ningún libro (no hay ninguno con ese título)"
# Esperado: NO CUMPLE a propósito, por buscar_por_titulo en biblioteca/libros.py
`,
    files: ['.gitignore', 'README.md', 'biblioteca/__init__.py', 'biblioteca/db.py', 'biblioteca/libros.py', 'biblioteca/prestamos.py', 'pyproject.toml', 'reglas_negocio.toml', 'requirements.txt', 'tests/test_reglas.py'],
  },
  'urielbatizzzzzzzz/crud-cafeteria': {
    content: `# reglas_negocio.toml — reglas de negocio de la Cafetería escolar (formato de IA VOY)
#
# Cada regla dice, en palabras de la cafetería, qué debe pasar siempre. IA VOY la comprueba de una de dos formas:
#   - con una PRUEBA: tests/test_reglas.py tiene una prueba marcada @pytest.mark.regla("RN-00X") que simula el caso
#     del \`criterio\` (Dado… cuando… entonces…). Si la prueba pasa, la regla se cumple.
#   - con un PATRÓN: un texto que NO debe aparecer en el código (\`prohibido\`) o que SÍ debe aparecer (\`obligatorio\`).

[proyecto]
nombre  = "Cafetería escolar"
version = "1.1"

[[regla]]
id          = "RN-001"
titulo      = "Los cobros salen exactos al centavo"
descripcion = "Lo que se cobra en caja coincide al centavo con la suma de los precios: 3 cafés de $25.50 son $76.50, ni un centavo más ni menos. Así el corte de caja siempre cuadra."
severidad   = "alta"
rutas       = ["cafeteria/"]
# PATRÓN: en el código de la cafetería no debe aparecer  float(  . Convertir dinero a float pierde centavos
# (en Python 0.1 + 0.2 da 0.30000000000000004); el dinero se maneja con Decimal("25.50").
prohibido   = 'float\\('
historia    = "HU-01 Cobrar una venta"
responsable = "Encargada de caja"
criterio    = "Dados 3 cafés de $25.50, cuando se cobran, entonces el total es exactamente $76.50"
# También la revisa la prueba test_total_exacto_al_centavo.
# Esperado: NO CUMPLE a propósito, por propina_sugerida en cafeteria/ventas.py

[[regla]]
id          = "RN-002"
titulo      = "No se vende lo que no hay"
descripcion = "Una venta no puede llevarse más piezas de las que hay en existencia. Si un producto del pedido no alcanza, se rechaza el pedido completo y no se descuenta nada del inventario."
severidad   = "alta"
historia    = "HU-02 Controlar existencias"
responsable = "Encargada de caja"
criterio    = "Dado que quedan 2 tortas, cuando un alumno pide 1 café y 3 tortas, entonces la venta se rechaza y siguen habiendo 10 cafés y 2 tortas"
# Se verifica con la prueba test_no_se_vende_lo_que_no_hay

[[regla]]
id          = "RN-003"
titulo      = "Solo el administrador cambia precios o borra productos"
descripcion = "Un cajero puede vender, pero no puede cambiar el precio de un producto ni borrarlo del menú. Esas operaciones están en cafeteria/admin.py y todas piden ser administrador."
severidad   = "media"
rutas       = ["cafeteria/admin.py"]
# PATRÓN: el archivo de administración debe usar  @requiere_admin , el candado que revisa que quien opera sea
# administrador. La prueba test_solo_admin_cambia_precio comprueba que el candado funciona de verdad.
obligatorio = '@requiere_admin'
historia    = "HU-04 Administrar el menú"
responsable = "Gerencia"
criterio    = "Dado que Pepe es cajero, cuando intenta cambiar el precio del café a $1.00, entonces el sistema se lo niega; cuando Lupita (administradora) lo cambia a $27.00, el cambio se guarda"

[[regla]]
id          = "RN-004"
titulo      = "El descuento máximo es de 20 %"
descripcion = "Ninguna venta lleva un descuento mayor al 20 % del total. Un descuento más alto lo tiene que autorizar la gerencia fuera del sistema."
severidad   = "media"
historia    = "HU-03 Aplicar descuentos"
responsable = "Gerencia"
criterio    = "Dada una torta de $40.00, cuando se aplica 20 % de descuento, entonces se cobran $32.00; cuando se intenta aplicar 25 %, entonces el sistema lo rechaza"
# Se verifica con la prueba test_descuento_maximo_20
`,
    files: ['.gitignore', 'README.md', 'cafeteria/__init__.py', 'cafeteria/admin.py', 'cafeteria/productos.py', 'cafeteria/ventas.py', 'pyproject.toml', 'reglas_negocio.toml', 'requirements.txt', 'tests/test_reglas.py'],
  },
  'urielbatizzzzzzzz/crud-papeleria': {
    content: `# reglas_negocio.toml — reglas de negocio de la Papelería escolar
# OJO: este archivo NO sigue el formato a propósito (repo de prueba de IA VOY).
# Es TOML válido, pero tiene 8 errores de formato, uno por bloque, marcados con "ERROR". Ver README.md.
# La versión sin errores está en ejemplos/reglas_negocio_corregido.toml.

[proyecto]
nombre  = "Papelería escolar"
version = "1.0"
autor   = "Equipo 11"                      # ERROR 1: [proyecto] solo admite nombre y version

[[regla]]
id          = "R1"                         # ERROR 2: el id debe ser RN- y 3 dígitos (RN-001)
titulo      = "El IVA se cobra exacto al centavo"
descripcion = "El IVA de cada venta es exactamente el 16 % del total, redondeado al centavo: en una venta de $76.50 el IVA es $12.24. Así el ticket cuadra con lo que se reporta al SAT."
severidad   = "alta"
rutas       = ["papeleria/"]
prohibido   = 'float\\('
criterio    = "Dada una venta de $76.50, cuando se calcula el IVA, entonces es exactamente $12.24"

[[regla]]
id          = "RN-002"
titulo      = "No se vende lo que no hay"
descripcion = "Una venta no puede sacar más piezas de las que hay en el inventario."
severidad   = "critica"                    # ERROR 3: la severidad solo puede ser alta, media o baja
criterio    = "Dado que quedan 3 lápices, cuando alguien compra 5, entonces la venta se rechaza"

[[regla]]
id          = "RN-003"
titulo      = "Ningún artículo cuesta $0 o menos"   # ERROR 4: falta \`descripcion\`, que es obligatoria
severidad   = "media"
criterio    = "Cuando se intenta dar de alta una goma con precio $0.00, entonces el sistema lo rechaza"

[[regla]]
id          = "RN-004"
titulo      = "La tasa de IVA se escribe en un solo lugar"
descripcion = "El 16 % de IVA se toma de la constante TASA_IVA (papeleria/impuestos.py). Nadie escribe 0.16 directo en las cuentas de ventas: si la tasa cambia, se cambia en un solo lugar y no queda ningún cálculo con la tasa vieja."
severidad   = "baja"
rutas       = "papeleria/ventas.py"        # ERROR 5: \`rutas\` es una lista: ["papeleria/ventas.py"]
prohibido   = '0\\.16'

[[regla]]
id          = "RN-005"
titulo      = "10 % de descuento por mayoreo desde 12 piezas"
descripcion = "Si en una venta se llevan 12 piezas o más del mismo artículo, ese artículo lleva 10 % de descuento. Con 11 piezas o menos se cobra el precio normal."
severidad   = "media"
prioridad   = 1                            # ERROR 6: \`prioridad\` no es un campo de las reglas
criterio    = "Dados lápices de $6.50, cuando se compran 12, entonces se cobran $70.20 (en lugar de $78.00); cuando se compran 11, se cobran $71.50"

[[regla]]
id          = "RN-006"
titulo      = "El cobro no redondea a mano"
descripcion = "El total y el IVA se redondean siempre al centavo de la misma forma (con Decimal). Nadie usa round() por su cuenta en ventas, porque redondea distinto y el ticket deja de cuadrar con la caja."
severidad   = "baja"
rutas       = ["papeleria/ventas.py"]
prohibido   = 'round('                     # ERROR 7: expresión regular inválida; el paréntesis va escapado: 'round\\('

[[regla]]
id          = "RN-006"                     # ERROR 8: RN-006 ya existe (debería ser RN-007)
titulo      = "Todo artículo tiene nombre"
descripcion = "No se puede dar de alta un artículo sin nombre (o solo con espacios): en el ticket y en el inventario aparecería una línea en blanco."
severidad   = "baja"
criterio    = "Cuando se intenta dar de alta un artículo con nombre «  », entonces el sistema lo rechaza"
`,
    files: ['.gitignore', 'README.md', 'ejemplos/reglas_negocio_corregido.toml', 'papeleria/__init__.py', 'papeleria/impuestos.py', 'papeleria/inventario.py', 'papeleria/ventas.py', 'pyproject.toml', 'reglas_negocio.toml', 'requirements.txt', 'tests/test_papeleria.py'],
  },
}
