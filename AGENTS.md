# Contexto para agentes (y para la próxima sesión)

## Qué es esto
API REST de gestión de tickets de soporte técnico. FastAPI + MongoDB (PyMongo) + SlowAPI + JWT.

## Comandos

```bash
# instalar
pip install -r requirements.txt

# correr (desarrollo) - modo demo: sin cluster, sin Docker, sin Redis
# en .env: MONGODB_FAKE=true
uvicorn main:app --reload --port 8000

# tests (no necesitan Mongo ni Redis: usan el fake en memoria)
pytest -q

# benchmark de latencia (p50/p95/p99/RPS)
python scripts/bench.py --concurrency 50 --requests 500

# verificar índices en Mongo real
python scripts/check_indexes.py

# migrar datos de la base vieja "suport" a "supportdesk"
python scripts/migrate_db.py --dry-run
python scripts/migrate_db.py --apply
```

## Estructura

```
config.py              # configuración central (lee .env)
main.py                # app FastAPI, lifespan, middlewares
database/client.py     # AsyncMongoClient + get_db()
database/fake.py       # MongoDB en memoria (modo demo y tests)
database/indexes.py    # creación de índices
models/                # Pydantic v2 (user, ticket)
routers/               # endpoints (auth, users, tickets)
services/              # security (hash+JWT), authz (RBAC), cache (Redis), ratelimit, audit, validators, schemas
utils/middlewares.py   # límite de body, headers de seguridad, tiempo de respuesta
tests/                 # fakes en memoria + suite
scripts/               # bench, check_indexes, migrate_db
docs/                  # PLAN.md, SECURITY.md, adr/
```

## Reglas del proyecto

1. **Nunca** commitear `.env`. Solo `.env.example` (placeholders). La URI de Mongo no sale del repo.
2. Todo acceso a Mongo es **async** (`await`) y pasa por `Depends(get_db())` → testeable con fakes.
3. Los endpoints protegidos usan `Depends(current_user)` / `require_soporte` / `require_admin`.
4. `rol` y `disabled` los asigna el servidor, nunca el cliente.
5. Los `response_model` son la barrera contra filtrar datos sensibles: no agregar campos sensibles.
6. Los strings de entrada siempre con `min_length`/`max_length`.
7. Cada fase del plan se commitea por separado; `docs/PLAN.md` se actualiza en el mismo commit.
8. Comentarios y mensajes de error en español.

## Estado actual

- Plan completo y aceptado: `docs/PLAN.md`.
- Checklist de seguridad y rotación de secretos: `docs/SECURITY.md`.
- Decisiones y su motivo: `docs/adr/`.
