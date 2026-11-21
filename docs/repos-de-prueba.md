# Repositorios de prueba

Conjunto estándar de repositorios **públicos, en Python y de tipo CRUD** para probar IA voy siempre con los
mismos datos: cada integrante analiza los mismos repos y compara contra la columna "Esperado". Se eligieron por
ser pequeños (se analizan en segundos), por cubrir Flask, FastAPI y Django, y porque juntos activan los
distintos caminos del análisis: Bandit, Ruff con corrección automática, corrección con IA, pruebas reales en el
sandbox y casos límite.

Revisados el 14 de noviembre de 2026 (rama y commit indicados). Los hallazgos esperados salen de los analizadores
estáticos de IA voy (Ruff con `E4,E7,E9,F,B,SIM,C4` y Bandit); los resultados de pytest dependen del sandbox y
no se verificaron aquí. Si un repo cambia, el número puede moverse: usa el commit para comparar.

> Solo se **analizan**: no copies su código a este repositorio. Varios no tienen licencia (todos los derechos
> son de su autor); analizarlos con la URL pública está bien, redistribuirlos no.

## Conjunto estándar

| # | Repositorio (rama · commit) | Stack | Tamaño | Qué prueba | Esperado |
|---|---|---|---|---|---|
| 1 | [sixhobbits/flask-crud-app](https://github.com/sixhobbits/flask-crud-app) (`master` · `5cc31df`) | Flask + SQLAlchemy | 1 `.py`, 61 líneas | Prueba de humo: el análisis más corto posible. Sin `requirements.txt` ni pruebas | 1 hallazgo: Bandit `B201` alta (`debug=True`), **Fix IA** |
| 2 | [macagua/example.flask.crud-app](https://github.com/macagua/example.flask.crud-app) (`master` · `923f891`) · MIT | Flask + SQLAlchemy | 1 `.py`, 98 líneas | Seguridad con `requirements.txt` instalable | 2: Bandit `B201` alta y `B104` media (0.0.0.0), **Fix IA** |
| 3 | [Pytest-with-Eric/pytest-fastapi-crud-example](https://github.com/Pytest-with-Eric/pytest-fastapi-crud-example) (`master` · `d47bb85`) | FastAPI + SQLAlchemy + SQLite | 9 `.py`, 462 líneas, 8 pruebas | **Pruebas reales en el sandbox** (SQLite, sin servicios externos) y cobertura | 5: Ruff `B008` (llamada en un default de FastAPI), **Fix IA**; pytest y coverage reales con `SANDBOX=wsl`/`docker` |
| 4 | [juanbeniteza/django-rest-framework-crud](https://github.com/juanbeniteza/django-rest-framework-crud) (`master` · `93854bc`) · MIT | Django REST Framework | 27 `.py`, 393 líneas | Django; mezcla de Fix automático y con IA | 6: Ruff `F401` ×4 (**Fix**) y Bandit `B105` ×2 (`SECRET_KEY` en el código, **Fix IA**) |
| 5 | [adnaanbheda/flask-crud](https://github.com/adnaanbheda/flask-crud) (`master` · `15430b9`) | Flask + JWT | 10 `.py`, 301 líneas | El más variado: muchas reglas distintas y dependencias en `Pipfile` | 13: Ruff `F401`, `E722`, `E402`, `F507`…; Bandit `B201`, `B105`, `B101`, `B112`. 3 **Fix**, 10 **Fix IA**. Sin `requirements.txt`: el sandbox no instala dependencias |

## Casos límite

| Repositorio (rama · commit) | Qué tiene de especial | Qué debe pasar |
|---|---|---|
| [CloudBytes-Academy/todo-api-fastapi](https://github.com/CloudBytes-Academy/todo-api-fastapi) (`main` · `b02a917`) · MIT | 10 imports sin usar en 3 archivos | Todos con **Fix** automático: sirve para probar "Corregir todo" en el editor y ver subir el score |
| [testdrivenio/fastapi-crud-sync](https://github.com/testdrivenio/fastapi-crud-sync) (`master` · `d0e0b64`) · MIT | Código y `requirements.txt` dentro de `src/`; pruebas con `monkeypatch` (sin base de datos) | 5 `B008` (**Fix IA**). Hoy el sandbox solo instala el `requirements.txt` de la raíz: las pruebas fallan al importar (`DEPS`/`ERROR`). Limitación conocida |
| [MihaelaAghirculesei/todo-api](https://github.com/MihaelaAghirculesei/todo-api) (`main` · `2e83df3`) · MIT | Backend en `backend/` con 6 archivos de pruebas (SQLite en memoria) | 4: Ruff `B008` ×3 y Bandit `B104`. Mismo caso que el anterior: dependencias en una subcarpeta |

## Cómo usarlos

1. Nuevo análisis → pega la URL y la rama de la tabla.
2. Compara el reporte con la columna "Esperado": número de hallazgos, reglas y si cada una dice **Fix** o
   **Fix IA**.
3. Para las pruebas (repo 3), analiza con el sandbox encendido (`SANDBOX=wsl` o `docker` en `backend/.env`).
   Con `SANDBOX=off`, pytest y coverage salen simulados.
4. Para las correcciones: abre un hallazgo → **Aplicar corrección automática** o **Corregir con IA** (necesita
   `GEMINI_API_KEY`) → revisa el diff en el editor → Guardar.

## Descartados

| Repositorio | Por qué no |
|---|---|
| SamWarden/user_service | Demasiado grande para pruebas rápidas (156 `.py`, 3 800 líneas) |
| testdrivenio/fastapi-crud-async, mongodb-developer/pymongo-fastapi-crud | Necesitan PostgreSQL o MongoDB corriendo para sus pruebas |
| rayed/django_crud, UskoKruM/django-crud-sqlite3, piinalpin/flask-crud, mohit7soni/fastapi-sqlite-crud | Funcionan, pero no aportan casos que no cubran los de arriba |
| Frameworks CRUD (Flask-AppBuilder, fastapi-crudrouter, fastcrud…) | Son bibliotecas, no aplicaciones CRUD |
