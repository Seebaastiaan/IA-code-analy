"""
Recomendaciones concretas por regla (en español) para los hallazgos de Bandit y Ruff.

Antes la recomendación decía "revisa la documentación de la regla" con un enlace: el usuario (y el asistente,
que la recibe en su contexto) se quedaba sin saber qué cambiar. Cada entrada dice POR QUÉ es un problema y QUÉ
cambiar, con el código de reemplazo cuando aplica. Las reglas de Ruff que no están en el catálogo usan la
explicación de su familia (app.analyses.familias): el ejemplo de la documentación de Ruff era genérico y en inglés.
"""

from app.analyses import familias

# (por qué, qué cambiar)
Remedy = tuple[str, str]

BANDIT: dict[str, Remedy] = {
    "B101": ("`assert` se elimina al correr Python con -O: la validación desaparece en producción.",
             "Cambia `assert condicion` por `if not condicion: raise ValueError(\"…\")` (o la excepción que corresponda)."),
    "B102": ("`exec` ejecuta como código cualquier texto: si una parte viene del usuario, puede correr lo que quiera.",
             "Quita `exec(...)`: llama directamente a la función que necesitas o usa un diccionario {nombre: función} para elegirla."),
    "B103": ("Permisos demasiado abiertos (p. ej. 0o777) dejan que cualquier usuario del sistema lea o modifique el archivo.",
             "Usa permisos mínimos: `os.chmod(ruta, 0o600)` para archivos privados o `0o644` si otros solo deben leerlo."),
    "B104": ("Escuchar en 0.0.0.0 expone el servicio en todas las interfaces de red, no solo en la máquina local.",
             "Usa `host=\"127.0.0.1\"` en desarrollo y toma el host de una variable de entorno: `host=os.getenv(\"HOST\", \"127.0.0.1\")`."),
    "B105": ("Una contraseña o clave escrita en el código queda en el historial de git: cualquiera con acceso al repo la ve.",
             "Léela del entorno: `SECRET_KEY = os.environ[\"SECRET_KEY\"]` (agrega `import os`), ponla en un `.env` fuera de git y rota la clave expuesta."),
    "B106": ("Pasar una contraseña literal como argumento la deja escrita en el código.",
             "Pasa el valor desde el entorno: `password=os.environ[\"DB_PASSWORD\"]` (agrega `import os`)."),
    "B107": ("Un valor por defecto con una contraseña deja una credencial fija en el código.",
             "Cambia el valor por defecto a `None` y, si llega `None`, léelo de `os.environ`."),
    "B108": ("Una ruta fija en /tmp es predecible: otro proceso puede crearla antes o leerla.",
             "Usa `tempfile.NamedTemporaryFile()` o `tempfile.mkdtemp()` (agrega `import tempfile`) en lugar de la ruta fija."),
    "B110": ("`except: pass` oculta los errores: el programa sigue en un estado incorrecto sin dejar rastro.",
             "Captura solo la excepción esperada y regístrala: `except ValueError as exc: logger.warning(\"…: %s\", exc)`."),
    "B112": ("`except: continue` salta errores sin registrarlos.",
             "Captura la excepción concreta y regístrala antes de `continue`: `except KeyError as exc: logger.warning(…); continue`."),
    "B113": ("Una petición HTTP sin `timeout` puede quedarse esperando para siempre y bloquear el proceso.",
             "Agrega un límite: `requests.get(url, timeout=10)` (lo mismo en post, put, delete…)."),
    "B201": ("Flask con `debug=True` abre la consola interactiva de Werkzeug: cualquiera que vea un error puede ejecutar código en el servidor.",
             "Cambia a `app.run(debug=os.getenv(\"FLASK_DEBUG\") == \"1\")` (agrega `import os`) y deja el modo debug apagado en producción."),
    "B202": ("`tarfile.extractall` sin filtro permite que un archivo malicioso escriba fuera de la carpeta destino (../).",
             "Usa `tar.extractall(destino, filter=\"data\")` (Python 3.12+) o valida cada miembro antes de extraerlo."),
    "B301": ("`pickle` ejecuta código al deserializar: cargar datos no confiables equivale a ejecutar lo que traigan.",
             "Guarda y lee los datos en JSON (`json.dumps` / `json.loads`); usa pickle solo con archivos que generó tu propio programa."),
    "B302": ("`marshal` no es seguro con datos externos.", "Usa `json` para intercambiar datos."),
    "B303": ("MD5 y SHA1 están rotos: se pueden fabricar colisiones.",
             "Usa `hashlib.sha256(...)`; para contraseñas, `bcrypt`, `argon2` o `hashlib.scrypt`."),
    "B304": ("Ese cifrado (DES, RC4, Blowfish…) es inseguro.", "Usa AES-GCM (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`) o `cryptography.fernet.Fernet`."),
    "B305": ("El modo ECB revela patrones de los datos cifrados.", "Usa un modo autenticado como GCM (`AESGCM`) o `Fernet`."),
    "B306": ("`tempfile.mktemp` crea un nombre que otro proceso puede ocupar antes (condición de carrera).",
             "Usa `tempfile.mkstemp()` o `tempfile.NamedTemporaryFile(delete=False)`."),
    "B307": ("`eval` ejecuta como código cualquier texto que reciba.",
             "Si solo conviertes un literal (número, lista, dict), usa `ast.literal_eval(texto)` (agrega `import ast`); si no, interpreta el valor sin ejecutarlo."),
    "B308": ("`mark_safe` desactiva el escape de HTML: con datos del usuario abre XSS.",
             "Quita `mark_safe` y deja que la plantilla escape; si necesitas HTML, construye con `format_html(\"<b>{}</b>\", valor)`."),
    "B310": ("`urllib.urlopen` también abre `file://` y otros esquemas: puede leer archivos locales con una URL manipulada.",
             "Valida que la URL empiece con `https://` antes de abrirla, o usa `requests.get(url, timeout=10)`."),
    "B311": ("`random` es predecible: no sirve para tokens, contraseñas ni códigos de verificación.",
             "Usa `secrets`: `secrets.token_urlsafe(32)` o `secrets.randbelow(n)` (agrega `import secrets`)."),
    "B312": ("Telnet envía todo, incluidas las contraseñas, sin cifrar.", "Usa SSH (`paramiko` o `asyncssh`)."),
    "B321": ("FTP envía credenciales y archivos sin cifrar.", "Usa SFTP (`paramiko`) o `ftplib.FTP_TLS`."),
    "B323": ("Un contexto SSL sin verificación acepta certificados falsos (ataque de intermediario).",
             "Usa `ssl.create_default_context()` en lugar de `ssl._create_unverified_context()`."),
    "B324": ("MD5 y SHA1 están rotos: no deben usarse para seguridad.",
             "Cambia a `hashlib.sha256(...)`; si el hash no es de seguridad (p. ej. una caché), indícalo con `hashlib.md5(datos, usedforsecurity=False)`."),
    "B401": ("Telnet no cifra la comunicación.", "Quita `telnetlib` y usa SSH (`paramiko`)."),
    "B403": ("`pickle` es inseguro con datos no confiables.", "Usa `json` para guardar o intercambiar datos."),
    "B404": ("`subprocess` ejecuta comandos del sistema: es un riesgo si alguna parte del comando viene del usuario.",
             "Úsalo solo con listas de argumentos fijas (`subprocess.run([\"git\", \"status\"], check=True)`) y nunca con `shell=True`."),
    "B405": ("`xml.etree` es vulnerable a XML maliciosos (bombas de entidades).", "Usa `defusedxml.ElementTree` (`pip install defusedxml`) con la misma API."),
    "B408": ("`xml.dom.minidom` es vulnerable a XML maliciosos.", "Usa `defusedxml.minidom`."),
    "B410": ("`lxml` resuelve entidades externas por defecto.", "Parsea con `lxml.etree.XMLParser(resolve_entities=False)` o usa `defusedxml`."),
    "B413": ("`pycrypto` ya no se mantiene y tiene vulnerabilidades conocidas.", "Cámbialo por `cryptography` (o `pycryptodome`)."),
    "B501": ("`verify=False` desactiva la validación del certificado: cualquiera en la red puede suplantar al servidor.",
             "Quita `verify=False`; si el servidor usa un certificado propio, pasa su CA: `verify=\"/ruta/ca.pem\"`."),
    "B502": ("Esa versión de SSL/TLS es insegura.", "Usa `ssl.create_default_context()` (TLS 1.2 o superior)."),
    "B503": ("Esa versión de SSL/TLS es insegura.", "Usa `ssl.create_default_context()` (TLS 1.2 o superior)."),
    "B504": ("Sin versión explícita puede negociarse un protocolo inseguro.", "Usa `ssl.create_default_context()`."),
    "B505": ("Una clave RSA/DSA menor a 2048 bits se puede romper.", "Genera la clave con `key_size=2048` o más (3072 recomendado)."),
    "B506": ("`yaml.load` puede construir objetos de Python arbitrarios y ejecutar código.", "Cambia a `yaml.safe_load(texto)`."),
    "B507": ("Aceptar cualquier clave del host permite conectarse a un servidor falso.",
             "Usa `client.set_missing_host_key_policy(paramiko.RejectPolicy())` y carga `client.load_system_host_keys()`."),
    "B601": ("Un comando de shell armado con datos externos permite inyectar comandos.", "Pasa los argumentos sin concatenarlos y valídalos contra una lista permitida."),
    "B602": ("`shell=True` deja que la shell interprete el comando: un valor del usuario puede agregar `; rm -rf …`.",
             "Quita `shell=True` y pasa una lista: `subprocess.run([\"ls\", \"-l\", ruta], check=True)`."),
    "B603": ("Ejecutar un programa externo es riesgoso si sus argumentos vienen del usuario.",
             "Mantén la lista de argumentos fija, valida los valores variables y usa la ruta completa del ejecutable."),
    "B604": ("`shell=True` permite inyección de comandos.", "Quita `shell=True` y pasa los argumentos como lista."),
    "B605": ("`os.system`/`os.popen` pasan el comando por la shell: permite inyección.",
             "Cámbialo por `subprocess.run([\"comando\", arg1], check=True)` (agrega `import subprocess`)."),
    "B606": ("Lanzar un proceso es riesgoso si los argumentos vienen del usuario.", "Valida los argumentos y usa la ruta completa del ejecutable."),
    "B607": ("Un ejecutable sin ruta completa se busca en el PATH: otro programa con el mismo nombre puede suplantarlo.",
             "Usa la ruta completa (`/usr/bin/git`) o `shutil.which(\"git\")` y verifica que exista."),
    "B608": ("Armar SQL concatenando o con f-strings permite inyección SQL: un valor como `1 OR 1=1` cambia la consulta.",
             "Usa parámetros: `cursor.execute(\"SELECT * FROM t WHERE id = ?\", (valor,))` (`%s` en PostgreSQL/MySQL) o el ORM."),
    "B609": ("Un comodín (*) en un comando de shell puede expandirse a nombres de archivo maliciosos.", "Pasa la lista de archivos explícita en lugar del comodín."),
    "B610": ("`QuerySet.extra` arma SQL a mano: riesgo de inyección.", "Reemplázalo por filtros del ORM (`filter`, `annotate`, `F()`, `Q()`)."),
    "B611": ("`RawSQL` con datos del usuario permite inyección.", "Pasa los valores en `params`: `RawSQL(\"… = %s\", (valor,))`, o usa el ORM."),
    "B612": ("`logging.config.listen` acepta configuración por red y puede ejecutar código.", "Quítalo o protégelo con `verify=` y escucha solo en 127.0.0.1."),
    "B613": ("Caracteres bidireccionales Unicode hacen que el código se vea distinto de lo que ejecuta.", "Elimina los caracteres de control Unicode de esa línea."),
    "B614": ("`torch.load` usa pickle: un modelo descargado puede ejecutar código.", "Usa `torch.load(ruta, weights_only=True)`."),
    "B615": ("Descargar de Hugging Face sin fijar la versión permite que cambie el contenido.", "Fija la revisión: `from_pretrained(modelo, revision=\"<hash del commit>\")`."),
    "B701": ("Jinja2 sin autoescape permite XSS con datos del usuario.",
             "Crea el entorno con `Environment(autoescape=select_autoescape([\"html\", \"xml\"]))`."),
    "B702": ("Mako no escapa HTML por defecto.", "Usa `default_filters=[\"h\"]` en la plantilla o cambia a Jinja2 con autoescape."),
    "B703": ("`mark_safe` desactiva el escape de HTML (XSS).", "Usa `format_html(...)` en lugar de `mark_safe(...)`."),
    "B704": ("`Markup` con datos del usuario permite XSS.", "Escapa los valores: `Markup(\"<b>{}</b>\").format(valor)` o `markupsafe.escape(valor)`."),
}

RUFF: dict[str, Remedy] = {
    # isort, pycodestyle y pyupgrade (los activa la configuración del propio repo)
    "I001": ("Los imports desordenados hacen difícil ver de qué depende el archivo y causan conflictos al juntar ramas.",
             "Ordénalos en tres grupos separados por una línea en blanco: biblioteca estándar, paquetes instalados y módulos del proyecto, cada uno en orden alfabético."),
    "E501": ("Una línea muy larga obliga a desplazarse para leerla y se revisa peor.", "Pártela en varias líneas (dentro de paréntesis) o saca una parte a una variable."),
    "W291": ("Los espacios al final de la línea ensucian los cambios en git.", "Bórralos; la mayoría de los editores lo hace al guardar."),
    "W293": ("Una línea en blanco con espacios ensucia los cambios en git.", "Deja la línea vacía, sin espacios."),
    "W292": ("Sin salto de línea al final, git marca la última línea como cambiada cada vez.", "Agrega un salto de línea al final del archivo."),
    # Pyflakes
    "F401": ("Un import que no se usa hace más lento el arranque y confunde sobre las dependencias reales.", "Borra el import (o agrégalo a `__all__` si es una reexportación intencional)."),
    "F403": ("`from x import *` oculta de dónde viene cada nombre y puede pisar otros.", "Importa solo lo que usas: `from x import a, b`."),
    "F405": ("El nombre puede venir de un `import *`: no se sabe de dónde sale.", "Reemplaza el `import *` por un import explícito de ese nombre."),
    "F541": ("Una f-string sin `{}` no interpola nada.", "Quita la `f` del inicio de la cadena."),
    "F601": ("La clave del diccionario está repetida: solo queda el último valor.", "Borra la entrada duplicada o cambia la clave."),
    "F632": ("`is` compara identidad, no valor: con números o cadenas puede fallar.", "Usa `==` (o `!=`) para comparar con literales."),
    "F811": ("Se redefine un nombre que ya existía sin haberlo usado: la primera definición queda muerta.", "Borra la definición duplicada o renombra una de las dos."),
    "F821": ("El nombre no está definido: esa línea lanzará NameError al ejecutarse.", "Define la variable, impórtala o corrige el nombre si es un error de escritura."),
    "F823": ("La variable local se usa antes de asignarse.", "Asígnala antes de usarla o declara `global`/`nonlocal` si es la de fuera."),
    "F841": ("Se asigna una variable que nunca se usa.", "Borra la asignación (deja solo la llamada si tiene efectos) o usa la variable."),
    "F842": ("Variable anotada que nunca se usa.", "Borra la anotación o usa la variable."),
    # pycodestyle
    "E401": ("Varios imports en una línea dificultan leer y ordenar.", "Pon un import por línea."),
    "E402": ("Un import que no está al inicio del módulo se ejecuta tarde y oculta dependencias.", "Mueve el import al inicio del archivo, junto a los demás."),
    "E701": ("Varias sentencias en una línea con `:` dificultan leer.", "Pasa el cuerpo del `if`/`for`/`def` a la línea siguiente, indentado."),
    "E702": ("Varias sentencias separadas por `;` en una línea.", "Pon cada sentencia en su propia línea."),
    "E703": ("El `;` al final sobra.", "Borra el punto y coma."),
    "E711": ("Comparar con `None` usando `==` puede dar resultados inesperados si la clase redefine `==`.", "Usa `is None` / `is not None`."),
    "E712": ("Comparar con `True`/`False` usando `==` es redundante.", "Usa la condición directa: `if activo:` / `if not activo:`."),
    "E713": ("`not x in y` se lee mal.", "Escribe `x not in y`."),
    "E714": ("`not x is y` se lee mal.", "Escribe `x is not y`."),
    "E721": ("Comparar tipos con `==` falla con subclases.", "Usa `isinstance(obj, Tipo)`."),
    "E722": ("`except:` captura todo, incluso Ctrl+C y errores de programación, y los oculta.", "Captura la excepción concreta: `except ValueError:` (o `except Exception:` como mínimo, y regístrala)."),
    "E731": ("Asignar una `lambda` a una variable pierde el nombre en los tracebacks.", "Defínela con `def nombre(args): return …`."),
    "E741": ("Nombres como `l`, `O` o `I` se confunden con 1 y 0.", "Renómbrala con un nombre descriptivo."),
    "E902": ("El archivo no se pudo leer.", "Revisa que exista y esté en UTF-8."),
    "E999": ("Error de sintaxis: el archivo no se puede ejecutar ni analizar.", "Corrige la sintaxis en esa línea (paréntesis, comillas o indentación)."),
    # flake8-bugbear
    "B002": ("Python no tiene `++`: `++x` es `+(+x)` y no incrementa nada.", "Usa `x += 1`."),
    "B003": ("Asignar `os.environ = …` no cambia el entorno de los procesos hijos.", "Usa `os.environ.clear()` / `os.environ.update(...)`."),
    "B004": ("`hasattr(x, \"__call__\")` no es confiable para saber si algo se puede llamar.", "Usa `callable(x)`."),
    "B005": ("`.strip(\"abc\")` quita esos caracteres sueltos, no la cadena completa.", "Usa `.removeprefix(\"abc\")` / `.removesuffix(\"abc\")`."),
    "B006": ("Un valor por defecto mutable (lista, dict) se crea una sola vez y se comparte entre llamadas.", "Usa `None` por defecto y crea el objeto dentro: `def f(x=None): x = [] if x is None else x`."),
    "B007": ("La variable del ciclo no se usa dentro.", "Renómbrala a `_` (o `_nombre`)."),
    "B008": ("Una llamada en un valor por defecto se evalúa una sola vez, al definir la función.", "Usa `None` por defecto y haz la llamada dentro; en FastAPI usa `Annotated[T, Depends(...)]`."),
    "B009": ("`getattr(obj, \"nombre\")` con un nombre fijo es más lento y menos claro.", "Escribe `obj.nombre`."),
    "B010": ("`setattr(obj, \"nombre\", v)` con un nombre fijo es menos claro.", "Escribe `obj.nombre = v`."),
    "B011": ("`assert False` desaparece con `python -O`.", "Usa `raise AssertionError(\"…\")`."),
    "B012": ("Un `return`/`break` en `finally` se traga la excepción.", "Saca el `return` del `finally`."),
    "B015": ("Una comparación suelta no hace nada (probablemente faltó `assert` o `if`).", "Agrega `assert` o usa el resultado."),
    "B017": ("`pytest.raises(Exception)` pasa con cualquier error, incluso uno no esperado.", "Indica la excepción concreta: `pytest.raises(ValueError)`."),
    "B018": ("Una expresión suelta no tiene efecto.", "Bórrala o asígnala/úsala."),
    "B019": ("`lru_cache` en un método mantiene vivas las instancias para siempre (fuga de memoria).", "Cachea una función fuera de la clase o usa `functools.cached_property`."),
    "B020": ("La variable del ciclo pisa el iterable que se recorre.", "Usa otro nombre para la variable del ciclo."),
    "B023": ("La función definida en el ciclo usa la variable del ciclo: todas verán el último valor.", "Pásala como argumento por defecto: `lambda x=x: …`."),
    "B024": ("Una clase abstracta sin métodos abstractos se puede instanciar.", "Marca al menos un método con `@abstractmethod` o quita `ABC`."),
    "B026": ("Un argumento con `*` después de palabras clave confunde el orden.", "Pasa los argumentos posicionales antes que los nombrados."),
    "B027": ("Método vacío en una clase abstracta sin `@abstractmethod`.", "Agrega `@abstractmethod` o una implementación."),
    "B028": ("`warnings.warn` sin `stacklevel` señala la línea equivocada.", "Agrega `stacklevel=2`."),
    "B904": ("Relanzar dentro de `except` sin `from` mezcla los tracebacks.", "Escribe `raise NuevoError(...) from exc` (o `from None`)."),
    "B905": ("`zip` sin `strict` corta en silencio si las listas tienen distinto tamaño.", "Usa `zip(a, b, strict=True)`."),
    # flake8-simplify
    "SIM101": ("Varios `isinstance` sobre la misma variable.", "Únelos: `isinstance(x, (A, B))`."),
    "SIM102": ("`if` anidados que se pueden unir.", "Únelos con `and` en un solo `if`."),
    "SIM103": ("`if c: return True else: return False` es redundante.", "Escribe `return c` (o `return bool(c)`)."),
    "SIM105": ("`try/except/pass` es más largo de lo necesario.", "Usa `with contextlib.suppress(Error):` (agrega `import contextlib`)."),
    "SIM113": ("Un contador que se suma a mano dentro del `for` puede desfasarse.", "Usa `for i, x in enumerate(items):` en lugar de llevar el índice a mano."),
    "SIM108": ("Un `if/else` que solo asigna un valor.", "Usa el ternario: `x = a if cond else b`."),
    "SIM110": ("Un ciclo que busca si algún elemento cumple.", "Usa `return any(cond(x) for x in items)`."),
    "SIM115": ("Abrir un archivo sin `with` puede dejarlo abierto si hay un error.", "Usa `with open(ruta) as f:`."),
    "SIM117": ("`with` anidados.", "Únelos: `with A() as a, B() as b:`."),
    "SIM118": ("`key in d.keys()` crea una vista innecesaria.", "Escribe `key in d`."),
    "SIM201": ("`not a == b` se lee mal.", "Escribe `a != b`."),
    "SIM210": ("`True if c else False` es redundante.", "Escribe `bool(c)`."),
    "SIM300": ("Comparación \"Yoda\" (`1 == x`).", "Escribe la variable primero: `x == 1`."),
    "SIM401": ("`if k in d: v = d[k] else: v = x` se puede simplificar.", "Usa `v = d.get(k, x)`."),
    "SIM910": ("`d.get(k, None)` es lo mismo que `d.get(k)`.", "Quita el `None`."),
}

# Prefijos de Ruff sin entrada propia
RUFF_PREFIX: dict[str, Remedy] = {
    "C4": ("La comprensión o la llamada a `list()`/`dict()`/`set()` sobra.", "Reescríbela como literal o comprensión directa (`[]`, `{}`, `{x for x in …}`)."),
    "SIM": ("El código se puede escribir de forma más simple.", "Simplifícalo como indica el mensaje de Ruff."),
}


def ruff_remedy(code: str, message: str) -> Remedy:
    """(por qué, qué hacer) en español: el catálogo, el prefijo conocido o la familia de la regla (app.analyses.familias)."""
    if code in RUFF:
        return RUFF[code]
    prefix = next((p for p in RUFF_PREFIX if code.startswith(p)), None)
    if prefix:
        return RUFF_PREFIX[prefix]
    _, why, rec = familias.family(code)
    return why, rec


def bandit_remedy(code: str, message: str) -> Remedy:
    if code in BANDIT:
        return BANDIT[code]
    what = "" if familias.english(message) else f" ({message})"
    return ("Bandit marcó un patrón que puede ser inseguro.", f"Revisa la línea señalada{what} y quita ese patrón. Si es un falso positivo comprobado, ignora {code} en Configuración.")
