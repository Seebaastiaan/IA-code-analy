# Prueba del sandbox con Docker

Responsable: Diego Salinas (IA & Analizadores) · Sprint 9

El sandbox WSL2 aísla del entorno de Windows pero no del disco (`/mnt/c`). Antes de abrir la app a personas
ajenas al equipo hay que usar `SANDBOX=docker`, que corre cada análisis en un contenedor desechable con el clon de
solo lectura (ADR-002). Esta prueba valida ese modo de punta a punta.

## Preparación

1. Docker Desktop corriendo (`docker info` responde).
2. Descargar la imagen una vez: `docker pull ghcr.io/astral-sh/uv:python3.12-bookworm-slim`.
3. En `backend/.env`: `SANDBOX=docker` y reiniciar el backend.
4. `GET /api/health` debe mostrar el servicio "Sandbox Docker · Activo".

## Casos

| # | Caso | Cómo | Esperado | Resultado |
|---|---|---|---|---|
| 1 | Análisis completo | Analizar el repo con `seed_data/demo_repo` | Mismos números que con WSL: 5 paquetes vulnerables, 2 pruebas pasan, cobertura medida | |
| 2 | Tiempo | Medir la duración del reporte | Comparable a WSL (anotar ambos) | |
| 3 | Solo lectura | Repo con una prueba que intenta escribir en `/src` | La escritura falla dentro del contenedor; el clon del editor no cambia | |
| 4 | Sin claves | Prueba que imprime `os.environ` | No aparecen `GITHUB_CLIENT_SECRET`, `GEMINI_API_KEY` ni `SECRET_KEY` | |
| 5 | Límite de memoria | Prueba que reserva 3 GB | El contenedor muere por memoria (2 GB); el análisis termina con el hallazgo de pytest | |
| 6 | Bomba de procesos | Prueba que hace `fork` en bucle | Se corta en 512 procesos; el backend sigue respondiendo | |
| 7 | Cancelar | Cancelar a mitad de las pruebas | `docker ps` ya no muestra el contenedor `ia-voy-…` | |
| 8 | Tiempo agotado | `SANDBOX_TIMEOUT_S=30` con pruebas lentas | El contenedor se detiene y el reporte lo indica | |
| 9 | Docker apagado | Cerrar Docker Desktop y analizar | Aviso "sandbox docker no disponible (Docker no está corriendo)" y pasos simulados | |

## Resultados

| Fecha | Máquina | Versión de Docker | Casos ✅ | Duración demo (WSL / Docker) | Notas |
|---|---|---|---|---|---|
| | | | /9 | | |

## Conclusión

Anotar si `SANDBOX=docker` queda como recomendado para el despliegue público (`docs/despliegue.md`, Sprint 10).
