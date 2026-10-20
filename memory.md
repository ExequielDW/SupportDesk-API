# MEMORY — contexto vivo del proyecto

<!-- autogenerado:cabecera -->
> **Actualizado:** 2026-10-20 19:22 · **Commit:** `e8005ba` · **Rama:** `master`
<!-- autogenerado:/cabecera -->

> Este archivo se actualiza al cerrar cada tarea (ver `AGENTS.md`, regla 9).
> Si contradice al código, **gana el código**: corregirlo es parte de la tarea.
> Las partes marcadas `[AUTO]` las regenera `python scripts/context.py --update`.

## 1. Qué es y cómo se corre

API REST de tickets de soporte. FastAPI + MongoDB (driver async) + SlowAPI + JWT + Redis (opcional).
Roles `usuario < soporte < admin`. Refresh tokens rotativos y revocables. 17 endpoints, 38 tests.

```bash
pip install -r requirements.txt
# .env con MONGODB_FAKE=true -> corre sin cluster, sin Docker y sin Redis
uvicorn main:app --reload --port 8000
pytest -q          # 38 tests, no necesitan Mongo ni Redis
ruff check .
```

## 2. Mapa del código

<!-- autogenerado:mapa -->
| Archivo | Qué hace |
| :--- | :--- |
| `.env.example` | plantilla de variables de entorno (sin secretos) |
| `.gitignore` | archivos excluidos de git |
| `AGENTS.md` | reglas del proyecto y cómo trabajar acá |
| `CHANGELOG.md` | historial de cambios por versión |
| `config.py` | Configuración central de la aplicación. |
| `database/client.py` | Cliente de MongoDB (asíncrono). |
| `database/fake.py` | MongoDB en memoria para correr la API sin ninguna infraestructura. |
| `database/indexes.py` | Índices de MongoDB. |
| `main.py` | Punto de entrada de la aplicación FastAPI. |
| `memory.md` | contexto vivo del proyecto (este archivo) |
| `models/ticket.py` | Modelos de ticket y reglas de transición de estado. |
| `models/user.py` | Modelos de usuario. |
| `README.md` | cara al público: qué es, cómo se usa y endpoints |
| `requirements.txt` | dependencias de Python |
| `routers/auth.py` | Infraestructura de autenticación compartida por los routers. |
| `routers/tickets.py` | Endpoints de tickets. |
| `routers/users.py` | Endpoints de usuarios: registro, login, refresh, logout y perfil. |
| `ruff.toml` | configuración del linter |
| `scripts/bench.py` | Benchmark de latencia de los endpoints hot. |
| `scripts/check_indexes.py` | Verifica que las queries hot usan índices (IXSCAN) y no collection scans. |
| `scripts/context.py` | Genera y actualiza las partes automáticas de `memory.md`. |
| `scripts/migrate_db.py` | Migra los datos de la base vieja a la base nueva. |
| `services/audit.py` | Auditoría de eventos de seguridad. |
| `services/authz.py` | Autenticación y autorización (RBAC). |
| `services/cache.py` | Cache compartido (Redis) con fallback en memoria. |
| `services/ratelimit.py` | Rate limiting por usuario (complementa el límite por IP de SlowAPI). |
| `services/schemas.py` | Formateadores de documentos de Mongo a diccionarios de Python. |
| `services/security.py` | Hashing de contraseñas y emisión/validación de tokens. |
| `services/validators.py` | Validaciones de negocio y acceso a datos. |
| `tests/conftest.py` | Fixtures de la suite. |
| `tests/test_auth.py` | Autenticación: login, refresh rotativo, revocación y anti-enumeración. |
| `tests/test_security.py` | Pruebas de seguridad: autorización, aislamiento, abuse y validación. |
| `tests/test_tickets.py` | Contrato HTTP de usuarios y tickets (con fake de Mongo en memoria). |
| `utils/middlewares.py` | Middlewares de la aplicación. |
<!-- autogenerado:/mapa -->

## 3. Superficie de la API

<!-- autogenerado:api -->
| Método | Ruta | Acceso | Qué hace |
| :--- | :--- | :--- | :--- |
| `GET` | `/tickets` | soporte/admin | Lista todos los tickets (soporte y admin) |
| `POST` | `/tickets/created` | autenticado | Crea un ticket |
| `GET` | `/tickets/me` | autenticado | Lista los tickets del usuario, con filtros y paginación |
| `GET` | `/tickets/me/{id}` | autenticado | Devuelve un ticket por id |
| `GET` | `/tickets/stats` | autenticado | Estadísticas de los tickets del usuario |
| `GET` | `/tickets/stats/global` | soporte/admin | Estadísticas de todos los tickets |
| `PUT` | `/tickets/update/{id}` | autenticado | Actualiza un ticket |
| `PATCH` | `/tickets/{id}/estado` | autenticado | Cambia el estado de un ticket |
| `POST` | `/usuarios/login` | público | Inicia sesión y devuelve un access token |
| `POST` | `/usuarios/logout` | público | Cierra la sesión y revoca los tokens |
| `GET` | `/usuarios/me` | autenticado | Devuelve el perfil del usuario autenticado |
| `POST` | `/usuarios/refresh` | público | Rota el refresh token y devuelve uno nuevo |
| `POST` | `/usuarios/register` | público | Registra un usuario nuevo |
| `PATCH` | `/usuarios/{id}/estado` | **admin** | Habilita o deshabilita una cuenta (solo admin) |
| `PATCH` | `/usuarios/{id}/rol` | **admin** | Asigna un rol a un usuario (solo admin) |

Base: `/` y `/health`. En `ENVIRONMENT=production` se agregan `/docs`, `/redoc` y `/openapi.json`.
<!-- autogenerado:/api -->

## 4. Decisiones vigentes

| Decisión | Por qué | Detalle |
| :--- | :--- | :--- |
| Driver async (`AsyncMongoClient`) | las queries bloqueaban el event loop | `docs/adr/0001` |
| RBAC `usuario < soporte < admin` | el soporte necesita atender tickets ajenos | `docs/adr/0002` |
| Access 15 min + refresh 7 días rotativo en cookie `httpOnly` | el token de 30 min no se podía revocar | `docs/adr/0003` |
| Índices: `username`/`email` únicos y `(propietario, titulo)` único | había collection scans y el título era único **global** | `docs/adr/0004` |
| Modo demo (`MONGODB_FAKE=true`) | correr sin cluster, sin Docker y sin Redis | `docs/adr/0005` |
| Argon2id `t=2, m=19 MiB, p=1` en threadpool | 44 ms/64 MB bloqueaban el loop; los hashes viejos siguen validando | `services/security.py` |
| Redis opcional con fallback en memoria | el proyecto no usa Docker | `services/cache.py` |
| `rol` y `disabled` los asigna el servidor | el cliente no puede auto-asignarse admin | `models/user.py` |

## 5. Reglas que no se negocian

Las reglas completas están en `AGENTS.md` (12). En corto: nunca commitear `.env` · todo acceso a
Mongo es `await` y pasa por `Depends(get_db())` · los endpoints protegidos usan `current_user` /
`require_soporte` / `require_admin` · `response_model` es la barrera contra filtrar datos ·
todo string de entrada con límites · una fase del plan = un commit · comentarios en español ·
`memory.md` se actualiza al cerrar cada tarea · una sola fuente por dato · cero secretos.

## 6. Preferencias del usuario

- **Idioma:** español latino (rioplatense informal) en comentarios, mensajes de error y documentación.
- **No usa Docker** y **no despliega en la web**: el proyecto se prueba en local y se publica en GitHub.
- **Redis es opcional**: cache en memoria por defecto está bien.
- **`.env` intocable**: la URI de Mongo nunca sale del repo; solo `.env.example` con placeholders.
- **Preguntar antes de decidir**: quiere que se le consulten las decisiones de diseño (arquitectura,
  seguridad, dependencias) antes de aplicarlas, y que los planes se lean antes de ejecutar.
- Valora que el plan quede **persistido en el repo** (no en el chat) para no perder contexto.

## 7. Skills y agentes

| Skill / agente | Para qué sirve | Qué se encontró en este proyecto |
| :--- | :--- | :--- |
| `customize-opencode` | configurar el propio opencode (`opencode.json`, `.opencode/`, agentes, skills, plugins) | no hizo falta: el proyecto no tiene configuración de opencode |
| `explore` (agente) | buscar en el codebase sin cargar todo el contexto | no hizo falta: el repo es chico y se leyó completo |
| `general` (agente) | tareas multi-paso | se usó para el refactor de rendimiento + seguridad |

Si el entorno suma skills o tipos de agente, hay que actualizar esta tabla.

## 8. Última implementación

**2026-10-20 — Contexto vivo del proyecto** (commits `8a…` → `origin/master`)

- `memory.md` nuevo (10 secciones: mapa del código, superficie de la API, decisiones, reglas,
  preferencias del usuario, skills y agentes, última implementación, deuda técnica y verificación).
- `AGENTS.md`: bloque "Cómo arrancar una sesión" + reglas 9-12 (contexto vivo, una sola fuente
  por dato, skills y preferencias, cero secretos).
- `scripts/context.py`: regenera desde el código real las partes `[AUTO]` de `memory.md`.
- Resúmenes en español en las 15 rutas de la API (mejoran `/docs` y la tabla de contexto).

**2026-10-20 — Rendimiento + seguridad + modo demo** (`51b2b75..e8005ba`, 8 commits a `origin/master`)

- Driver async, 5 índices, cache de usuario y estadísticas, paginación, `orjson`, Argon2 ajustado.
- Access + refresh rotativo con revocación y detección de reuso; RBAC; rate limit por usuario;
  auditoría; headers de seguridad; límite de body; `/docs` off con `ENVIRONMENT=production`.
- 3 bugs corregidos: el `PUT` de tickets borraba `estado` (500), el título era único global
  (fuga de información) y el límite por usuario contaba los intentos correctos.
- Modo demo con MongoDB en memoria (`database/fake.py`): la API corre sin cluster ni Docker.
- Documentación: `docs/PLAN.md`, `docs/SECURITY.md`, 5 ADRs, `AGENTS.md`, `CHANGELOG.md`.

## 9. Deuda técnica y pendientes

- **El cluster de Atlas anterior ya no existe** (`mongoa.i8jibjk.mongodb.net` no resuelve). Para
  datos reales: crear un cluster nuevo, poner la URI y `MONGODB_FAKE=false`.
- **Cache en memoria**: es por proceso (no se comparte entre workers) y los refresh tokens se
  pierden al reiniciar. Con Redis se resuelve.
- **`GET /tickets`** (listado global) ordena por `ultima_actualizacion` sin índice propio:
  con muchos tickets el sort queda en memoria.
- El limiter de **SlowAPI** usa storage en memoria: con N workers el límite real es N× el configurado.
- **Sin verificación de email ni reset de password** (no hay envío de emails).
- **Sin adjuntos** en tickets: el límite de body de 100 KB es deliberado.
- `services/schemas.py` quedó parcialmente redundante con los serializers de los routers.

## 10. Verificación

<!-- autogenerado:verificacion -->
| Comprobación | Resultado |
| :--- | :--- |
| Tests | 38 passed |
| Lint (ruff) | sin hallazgos |
| Rutas registradas | 17 operaciones en 17 paths |
<!-- autogenerado:/verificacion -->
