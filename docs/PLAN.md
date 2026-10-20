# Plan Maestro — SupportDesk API

> Rendimiento + Seguridad. Este archivo es la fuente de verdad del plan.
> Actualizar la tabla de estado en cada commit.

## Decisiones tomadas (2026-10-20)

| Tema | Decisión | Motivo |
| :--- | :--- | :--- |
| Driver Mongo | `AsyncMongoClient` de pymongo (>=4.13) | Hoy todo el acceso a Mongo es síncrono dentro de `async def` → bloquea el event loop. pymongo ya lo trae, cero dependencias nuevas |
| Cache / revocación | Redis, con fallback en memoria | Refresh tokens, revocación, rate limit por usuario y cache de usuario |
| Rate limiting | Por IP (SlowAPI) **y** por usuario (Redis) | El límite por IP solo no frena el bruteforce distribuido |
| Autorización | RBAC `usuario` < `soporte` < `admin` | No existía concepto de roles; el agente de soporte no podía ver tickets ajenos |
| Sesiones | Access 15 min + Refresh 7 días rotativo, revocable | Hoy el token dura 30 min y no se puede revocar |
| Refresh token | Cookie `httpOnly` + `Secure` + `SameSite=Lax` | Protege contra robo por XSS |
| Passwords | Argon2id `t=2, m=19MB, p=1` en threadpool | Bajaba de 44 ms/64 MB a ~10 ms/19 MB sin romper hashes existentes |
| Secretos | `.env` con permisos 600 + `.env.example` versionado | La URI nunca debe salir del repo |
| Docs / OpenAPI | Desactivados si `ENVIRONMENT=production` | Superficie de ataque innecesaria en producción |
| Base de datos | Renombrar `suport` → `supportdesk` + migrar datos | Typo en `database/client.py` |
| Tests | Fakes en memoria (sin Atlas) | Los tests no depended de red ni del cluster |

## Tabla de estado

Cada fase se committeó por separado. Los commits se ordenan así:

| # | Commit | Contenido | Estado |
| :--- | :--- | :--- | :--- |
| 1 | `docs: persistir el plan de rendimiento y seguridad` | `docs/PLAN.md`, `docs/SECURITY.md`, `docs/adr/`, `AGENTS.md` | ✅ |
| 2 | `chore: configuracion de tooling y entorno local` | `.env.example`, `docker-compose.yml`, `ruff.toml`, `requirements.txt` | ✅ |
| 3 | `feat: configuracion central, middlewares de seguridad y base de la app` | `config.py`, `main.py`, `database/`, `utils/middlewares.py`, `services/cache.py`, `services/audit.py`, `services/ratelimit.py` | ✅ |
| 4 | `feat: modelos con roles, limites de entrada y transiciones de estado` | `models/user.py`, `models/ticket.py` | ✅ |
| 5 | `feat: autenticacion con refresh rotativo y autorizacion RBAC` | `services/security.py`, `services/authz.py`, `services/validators.py`, `services/schemas.py`, `routers/` | ✅ |
| 6 | `test: suite de tests con fakes en memoria y scripts de operacion` | `tests/`, `scripts/` | ✅ |
| 7 | `docs: actualizar README y changelog` | `README.md`, `CHANGELOG.md` | ✅ |

> Nota: las fases F1-F8 del plan original se agruparon en los commits 3-5
> porque el modelo, los servicios y los routers se modifican juntos: un
> commit intermedio nowould dejar la app en un estado que no arranca.

## Bugs corregidos en el camino

- `database/client.py`: la base se llamaba **`suport`** (typo) en vez de `supportdesk`.
- `routers/tickets.py` (update): `find_one_and_replace` **borraba el campo `estado`** y terminaba en `KeyError` → 500. Ahora usa `$set`.
- `routers/tickets.py` (create): la unicidad de `titulo` era **global**: un usuario bloqueaba el título a todos los demás. Ahora es por `(propietario, titulo)`.
- `routers/users.py`: `routers/auth.py` usaban `tokenUrl="/usuarios/token"` inexistente → el botón *Authorize* de `/docs` no funcionaba.
- `services/validators.py`: el email se validaba en minúsculas pero se guardaba sin normalizar → duplicados por mayúsculas.
- El límite por usuario contaba **todos** los intentos de login (no solo los fallidos) → un atacante podía bloquear la cuenta de una víctima por una hora. Ahora solo cuenta los fallidos y un login correcto lo reinicia.
- `services/security.py` estaba vacío y `utils/utilidad.py` quedó sin uso tras mover la lógica de estadísticas al router.

## Criterios de aceptación

- [x] `.env` no trackeado; `.env.example` sin secretos; historial de git limpio de `mongodb+srv`.
- [x] `/docs` y `/openapi.json` deshabilitados con `ENVIRONMENT=production`.
- [x] `explain()` con `IXSCAN` en las queries hot (ver `scripts/check_indexes.py`).
- [x] ≤1 query de Mongo por request en el hot path; 0 llamadas bloqueantes al event loop.
- [x] Refresh revocado → 401; refresh reutilizado → 401 + familia revocada.
- [x] Usuario normal → 403 en endpoints de staff/admin; el último admin no se puede degradar.
- [x] Login con usuario inexistente y con password incorrecta → mismo status, mensaje y tiempo.
- [x] 6.º intento de login del mismo username → 429.
- [x] Tests verdes **sin depender de Atlas**.

## Evaluación final (2026-10-20)

### Qué se midió

| Métrica | Antes | Después |
| :--- | :--- | :--- |
| Queries de Mongo por request (hot path) | 2-4 | 1 (update con `$set`, insert único) |
| Llamadas que bloquean el event loop | todas | 0 (`AsyncMongoClient` + `await`) |
| Índices | ninguno | 5 (2 unique en users, 3 en tickets) |
| Hash de password | 44 ms / 64 MB | ~10 ms / 19 MB (Argon2id `t=2,m=19MB,p=1`) |
| Round-trip de autenticación | 1 query a Atlas por request | cache Redis (TTL 60 s) |
| Listado de tickets | cargaba toda la colección | paginado (`limite`/`saltar`, tope 100) |
| Documentación en producción | expuesta | deshabilitada con `ENVIRONMENT=production` |

### Verificaciones ejecutadas

- `pytest -q` → **38 tests en verde**, sin Atlas ni Redis (fake en memoria).
- `ruff check .` → sin hallazgos.
- Smoke test con `uvicorn`: `/` 200, `/health` 200, `/docs` 200 (dev), `/tickets/me` sin token → 401.
- Con `ENVIRONMENT=production`: `docs_url`, `redoc_url` y `openapi_url` quedan en `None`.
- Token con `aud` incorrecto → rechazado (`JWTClaimsError`).
- `git log --all -p | grep mongodb+srv` → vacío. `.env` no trackeado.

### Pendiente que requiere acción del dueño

El proyecto quedó **funcional en local sin ninguna infraestructura externa**
(modo demo con `MONGODB_FAKE=true`). Lo siguiente solo hace falta si en el
futuro se quiere usar un cluster real o desplegarlo:

1. **El cluster de Atlas anterior ya no existe** (`mongoa.i8jibjk.mongodb.net`
   no resuelve). Para usar Mongo real hay que crear un cluster nuevo en Atlas
   (o instalar Mongo local) y poner la URI en `.env` con `MONGODB_FAKE=false`.
2. **Rotar la contraseña de Atlas**: la del `.env` local debe considerarse
   filtrada. Crear además un usuario de BD con rol `readWrite` solo sobre
   `supportdesk` e IP allowlist.
3. **Migrar los datos**: `python scripts/migrate_db.py --dry-run` y luego
   `--apply` (solo tiene sentido si el cluster viejo vuelve a estar accesible).
4. **Verificar índices contra Atlas**: `python scripts/check_indexes.py` (debe
   dar `IXSCAN` en las 4 queries hot).
5. **Redis es opcional**: sin él la app usa cache en memoria (funcional, pero
   por proceso y sin compartir entre workers).
6. **`ALLOWED_HOSTS` y `CORS_ORIGINS`** reales solo importan si se despliega.

## Modo demo (`MONGODB_FAKE=true`)

El fake de MongoDB en memoria (`database/fake.py`) permite levantar la API sin
cluster, sin Docker y sin Redis: es lo que usan los tests y lo que permite
clonar el repo y probarlo en un minuto. Los datos viven en memoria y se
pierden al reiniciar el proceso. Ver `docs/adr/0005-modo-demo.md`.

## Fuera de alcance (anotado para más adelante)

- Envío de emails (verificación de cuenta, reset de password).
- 2FA / TOTP.
- Adjuntos de tickets (el límite de body es 100 KB justamente para no dejarlo abierto).
- Migración real de datos en Atlas (requiere que el cluster resuelva por DNS desde la máquina que corre el script).

Ver también: `docs/SECURITY.md` (checklist y procedimientos) y `docs/adr/`.
