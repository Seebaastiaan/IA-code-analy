import type { Finding } from '@/features/findings/types'

export type FindingTemplate = Omit<Finding, 'status' | 'snippet'>

/** Correcciones automáticas por id de hallazgo: [archivo, línea, texto nuevo | null] */
export const FIXES: Record<number, [string, number, string | null][]> = {
  1: [['auth.py', 15, '    SECRET_KEY = os.environ["SECRET_KEY"]']],
  2: [
    ['api.py', 17, '    consulta = "SELECT * FROM pagos WHERE cliente = ?"'],
    ['api.py', 18, '    filas = cursor.execute(consulta, (cliente,)).fetchall()'],
  ],
  3: [['requirements.txt', 4, 'requests==2.32.3']],
  4: [['utils.py', 9, '    return hashlib.sha256(datos).hexdigest()']],
  5: [
    ['tokens.py', 1, 'import secrets'],
    ['tokens.py', 9, '    return "".join(secrets.choice(ALFABETO) for _ in range(longitud))'],
  ],
  9: [['api.py', 3, null]],
  10: [
    [
      'pagos/procesador.py',
      38,
      '        resultado["ok"].append(\n            {"id": pago["id"], "monto": Decimal(pago["monto"]), "moneda": pago["moneda"], "estado": "cobrado"}\n        )',
    ],
  ],
  11: [
    ['utils.py', 17, 'def agregar(item, lista=None):'],
    ['utils.py', 18, '    lista = [] if lista is None else lista\n    lista.append(item)'],
  ],
}

export const FINDINGS: FindingTemplate[] = [
  { id: 1, sev: 'alta', cat: 'seg', tool: 'Bandit', rule: 'B105', file: 'auth.py', line: 15, fix: true,
    msg: 'Clave secreta escrita directamente en el código',
    why: 'Cualquier persona con acceso al repositorio puede firmar tokens JWT válidos y suplantar usuarios.',
    rec: 'Leer la clave desde una variable de entorno y rotar la clave expuesta.' },
  { id: 2, sev: 'alta', cat: 'seg', tool: 'Bandit', rule: 'B608', file: 'api.py', line: 17, fix: true,
    msg: 'Posible inyección SQL por concatenación de cadenas',
    why: 'El valor de "cliente" llega desde la URL y se inserta sin escapar en la consulta.',
    rec: 'Usar consultas parametrizadas con marcadores "?".' },
  { id: 3, sev: 'alta', cat: 'seg', tool: 'pip-audit', rule: 'requests 2.25.1', file: 'requirements.txt', line: 4, fix: true,
    msg: 'Dependencia con vulnerabilidad conocida',
    why: 'La versión instalada tiene avisos de seguridad publicados.',
    rec: 'Actualizar a la versión más reciente sin avisos y volver a correr las pruebas.' },
  { id: 4, sev: 'media', cat: 'seg', tool: 'Bandit', rule: 'B324', file: 'utils.py', line: 9, fix: true,
    msg: 'Hash débil (MD5) usado para validar contraseñas',
    why: 'MD5 tiene colisiones conocidas y es demasiado rápido para proteger contraseñas.',
    rec: 'Usar SHA-256 para huellas, o bcrypt/argon2 si es una contraseña.' },
  { id: 5, sev: 'media', cat: 'seg', tool: 'Bandit', rule: 'B311', file: 'tokens.py', line: 9, fix: true,
    msg: 'random no es criptográficamente seguro',
    why: 'Los tokens generados con random pueden predecirse.',
    rec: 'Usar el módulo secrets (secrets.choice o secrets.token_urlsafe).' },
  { id: 6, sev: 'media', cat: 'test', tool: 'coverage', rule: 'COV', file: 'pagos/reembolsos.py', line: 1, fix: false,
    msg: 'Cobertura de 31 % (umbral: 60 %)',
    why: 'La lógica de reembolsos casi no tiene pruebas y maneja dinero.',
    rec: 'Agregar pruebas para los casos de reembolso parcial y total.' },
  { id: 7, sev: 'media', cat: 'test', tool: 'pytest', rule: 'FAIL', file: 'tests/test_api.py', line: 13, fix: false,
    msg: 'test_crear_pago_invalido falló (AssertionError)',
    why: 'Una prueba fallida indica que el comportamiento esperado cambió o hay un error.',
    rec: 'Revisar el código de estado esperado (400 vs 422).' },
  { id: 8, sev: 'media', cat: 'prac', tool: 'Radon', rule: 'CC · D', file: 'pagos/procesador.py', line: 20, fix: false,
    msg: 'Complejidad ciclomática 24 en procesar_lote()',
    why: 'Funciones muy complejas son difíciles de probar y mantener.',
    rec: 'Dividir la función en pasos más pequeños (validar, agrupar, cobrar).' },
  { id: 9, sev: 'baja', cat: 'prac', tool: 'Ruff', rule: 'F401', file: 'api.py', line: 3, fix: true,
    msg: 'Import sin usar: os',
    why: 'Código muerto que confunde a quien lee el archivo.',
    rec: 'Eliminar el import.' },
  { id: 10, sev: 'baja', cat: 'prac', tool: 'Ruff', rule: 'E501', file: 'pagos/procesador.py', line: 38, fix: true,
    msg: 'Línea demasiado larga (128 > 100)',
    why: 'Dificulta la lectura y las revisiones de código.',
    rec: 'Partir la expresión en varias líneas.' },
  { id: 11, sev: 'baja', cat: 'prac', tool: 'Ruff', rule: 'B006', file: 'utils.py', line: 17, fix: true,
    msg: 'Argumento por defecto mutable',
    why: 'La lista por defecto se comparte entre llamadas y acumula valores.',
    rec: 'Usar None como valor por defecto y crear la lista dentro.' },
  { id: 12, sev: 'baja', cat: 'test', tool: 'pytest', rule: 'SKIP', file: 'tests/test_auth.py', line: 6, fix: false,
    msg: '3 pruebas omitidas con @skip',
    why: 'Pruebas omitidas pueden ocultar regresiones.',
    rec: 'Reactivarlas o documentar por qué se omiten.' },
]

/** Hallazgos resueltos en el análisis actual respecto al anterior (para la comparativa). */
export const RESOLVED_BEFORE: FindingTemplate[] = [
  { id: 101, sev: 'alta', cat: 'seg', tool: 'Bandit', rule: 'B201', file: 'app.py', line: 12, fix: false,
    msg: 'Flask con debug=True en producción', why: '', rec: '' },
  { id: 102, sev: 'baja', cat: 'prac', tool: 'Ruff', rule: 'F841', file: 'pagos/procesador.py', line: 40, fix: false,
    msg: 'Variable asignada y nunca usada', why: '', rec: '' },
]

export const COVERAGE = [
  { file: 'auth.py', percent: 92 },
  { file: 'utils.py', percent: 88 },
  { file: 'api.py', percent: 81 },
  { file: 'tokens.py', percent: 74 },
  { file: 'pagos/procesador.py', percent: 69 },
  { file: 'pagos/reembolsos.py', percent: 31 },
]

export const COMPLEXITY = [
  { fn: 'procesar_lote', file: 'pagos/procesador.py', cc: 24, grade: 'D' as const },
  { fn: 'validar_tarjeta', file: 'pagos/procesador.py', cc: 14, grade: 'C' as const },
  { fn: 'calcular_reembolso', file: 'pagos/reembolsos.py', cc: 11, grade: 'C' as const },
  { fn: 'crear_token', file: 'auth.py', cc: 3, grade: 'A' as const },
  { fn: 'listar_pagos', file: 'api.py', cc: 4, grade: 'A' as const },
  { fn: 'huella', file: 'utils.py', cc: 1, grade: 'A' as const },
]
