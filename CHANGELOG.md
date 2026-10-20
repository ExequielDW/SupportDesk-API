# Changelog

Todas las novedades de este proyecto.

## [1.0.0] — Rendimiento y seguridad

### Agregado
- **Modo demo** (`MONGODB_FAKE=true`): la API completa levanta con un MongoDB en memoria, sin cluster, sin Docker y sin Redis. Ver `docs/adr/0005-modo-demo.md`.
- Autenticación con access token (15 min) + refresh token rotativo (7 días) en cookie `httpOnly`, con allowlist en Redis, revocación real (logout) y detección de reuso que revoca la familia de tokens.
- Autorización RBAC con roles `usuario` / `soporte` / `admin`, dependencias `require_soporte` y `require_admin`, protección anti-escalación y regla del último administrador.
- Endpoints nuevos: `POST /usuarios/refresh`, `POST /usuarios/logout`, `PATCH /usuarios/{id}/rol`, `PATCH /usuarios/{id}/estado`, `GET /tickets` (global), `GET /tickets/stats/global`, `PATCH /tickets/{id}/estado`.
- Cambios de estado de ticket con transiciones validadas (reabrir es exclusivo de admin).
- Rate limiting por usuario (además del límite por IP) y auditoría de eventos de seguridad.
- Índices de MongoDB: `username` y `email` únicos, `(propietario, titulo)` único, `(propietario, estado)` y `(propietario, ultima_actualizacion)`.
- Cache de usuario y de estadísticas, paginación en los listados y respuestas con `orjson`.
- Middlewares: límite de tamaño del body, headers de seguridad y tiempo de procesamiento por request.
- `docs/PLAN.md`, `docs/SECURITY.md`, `docs/adr/`, `AGENTS.md`, `.env.example` y `docker-compose.yml`.
- Scripts: `bench.py`, `check_indexes.py`, `migrate_db.py`.
- Suite de tests sobre un fake de Mongo en memoria (36 tests, sin necesidad de Atlas ni Redis).

### Cambiado
- El fake de MongoDB pasó de `tests/fakes.py` a `database/fake.py`, para que la app y los tests usen la misma implementación.
- Redis es **opcional**: sin `REDIS_URL` la app usa un cache en memoria (funcional, pero por proceso).
- Migración del driver a `AsyncMongoClient` (pymongo >= 4.13): el acceso a datos ya no bloquea el event loop.
- El nombre de la base sale de `DB_NAME` (antes estaba hardcodeado como `suport`).
- Hashing de contraseñas con Argon2id `t=2, m=19 MiB, p=1` ejecutado en un threadpool (antes `t=3, m=64 MiB` dentro del event loop). Los hashes existentes siguen validando.
- `role` y `disabled` ya no se aceptan desde el cuerpo de las peticiones.
- Límites de longitud en todos los strings de entrada y username normalizado en minúsculas.
- `/docs`, `/redoc` y `/openapi.json` se deshabilitan con `ENVIRONMENT=production`.
- CORS con allowlist explícita (nunca `*`) y `TrustedHostMiddleware`.

### Corregido
- `PUT /tickets/update/{id}` borraba el campo `estado` del documento y terminaba en un error 500: ahora usa `$set`.
- La unicidad del título de un ticket era **global**: un usuario bloqueaba el título a todos los demás y se filtraba información entre usuarios. Ahora es por propietario.
- `tokenUrl` apuntaba a `/usuarios/token` (ruta inexistente): el botón *Authorize* de `/docs` no funcionaba.
- El email se validaba en minúsculas pero se guardaba sin normalizar: se podían registrar duplicados por mayúsculas.
- El login no distinguía entre usuario inexistente y contraseña incorrecta (anti-enumeración) y no tenía límite por usuario.
- `services/security.py` estaba vacío y `services/schemas.py` tenía funciones sin usar.
