import type { DiagnosticoResponse } from '@/features/diagnostico/types'
import { FILES } from './code'

/** Respuesta simulada de la IA para el prototipo de diagnóstico (mismos problemas que el repo de ejemplo). */
const HALLAZGOS: Record<string, DiagnosticoResponse['diagnostico']> = {
  'auth.py': {
    resumen: 'La clave para firmar los tokens está escrita en el código y las contraseñas se comparan con MD5.',
    score: 58,
    hallazgos: [
      { categoria: 'seg', severidad: 'alta', linea: 15, regla: 'HARDCODED-SECRET', mensaje: 'Clave secreta escrita directamente en el código', recomendacion: 'Léela de una variable de entorno y rota la clave expuesta.' },
      { categoria: 'seg', severidad: 'media', linea: 25, regla: 'WEAK-HASH', mensaje: 'MD5 no sirve para validar contraseñas', recomendacion: 'Usa bcrypt o argon2.' },
      { categoria: 'test', severidad: 'media', linea: 18, regla: 'UNTESTED', mensaje: 'crear_token no tiene pruebas para tokens expirados', recomendacion: 'Agrega una prueba con una fecha de expiración pasada.' },
      { categoria: 'prac', severidad: 'baja', linea: 2, regla: 'UNUSED-IMPORT', mensaje: 'Import sin usar: os', recomendacion: 'Elimina el import.' },
    ],
  },
}

const GENERICO: DiagnosticoResponse['diagnostico'] = {
  resumen: 'El archivo no tiene problemas graves; hay detalles de estilo.',
  score: 84,
  hallazgos: [{ categoria: 'prac', severidad: 'baja', linea: 1, regla: 'MISSING-DOCSTRING', mensaje: 'El módulo no tiene docstring', recomendacion: 'Describe en una línea qué hace el módulo.' }],
}

export function diagnostico(url: string, branch: string, file: string): DiagnosticoResponse {
  return {
    repo: url.replace(/^https:\/\/github\.com\//, '').replace(/\.git$/, ''),
    branch,
    commit: 'a3f9c1e',
    file,
    files: Object.keys(FILES).filter((f) => f.endsWith('.py')),
    model: 'Gemini 3.8 Flash',
    diagnostico: HALLAZGOS[file] ?? GENERICO,
  }
}
