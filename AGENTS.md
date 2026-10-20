# Contexto para agentes (y para la próxima sesión)

## Cómo arrancar una sesión (para no gastar tokens)

1. Leé este archivo y después `memory.md` (estado real del proyecto).
2. `memory.md` ya te dice qué existe, qué se decidió y qué quedó pendiente:
   no explores el repo entero ni releas los docs.
3. Abrí solo los archivos que la tarea toque.
4. Al terminar, actualizá `memory.md` (regla 9) y commitealo junto al código.

## Qué es esto
API REST de gestión de tickets de soporte técnico. FastAPI + MongoDB (PyMongo async) + SlowAPI + JWT.
Roles `usuario < soporte < admin`, sesiones revocables y tests que corren sin base de datos.

## Comandos

```bash
# instalar
pip install -r requirements.txt

# correr (desarrollo) - modo demo: sin cluster, sin Docker, sin Redis
# en .env: MONGODB_FAKE=true
uvicorn main:app --reload --port 8000

# tests (no necesitan Mongo ni Redis: usan el fake en memoria)
pytest -q

# lint
ruff check .

# contexto del proyecto: imprime / actualiza / verifica memory.md
python scripts/context.py
python scripts/context.py --update
python scripts/context.py --check

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
memory.md             # contexto vivo del proyecto (leelo primero)
database/client.py     # AsyncMongoClient + get_db()
database/fake.py       # MongoDB en memoria (modo demo y tests)
database/indexes.py    # creación de índices
models/                # Pydantic v2 (user, ticket)
routers/               # endpoints (auth, users, tickets)
services/              # security (hash+JWT), authz (RBAC), cache (Redis), ratelimit, audit, validators, schemas
utils/middlewares.py   # límite de body, headers de seguridad, tiempo de respuesta
tests/                 # fakes en memoria + suite
scripts/               # bench, check_indexes, migrate_db, context
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
9. **Contexto vivo.** Al cerrar cada tarea actualizá `memory.md` con lo que realmente cambió: archivos tocados, endpoints o reglas modificados, decisiones tomadas, bugs corregidos y pendientes. Si no cambió nada, no lo toques. `memory.md` nunca debe contradecir al código: si lo contradice, corregirlo es parte de la tarea.
10. **Una sola fuente por dato.** `AGENTS.md` = reglas · `memory.md` = estado actual · `docs/PLAN.md` = plan y fases · `docs/SECURITY.md` = checklist de seguridad · `docs/adr/` = decisiones y su motivo · `CHANGELOG.md` = historial. Si un dato está en dos lugares, es un bug de documentación: dejalo en uno y enlazalo.
11. **Skills, agentes y preferencias.** Anotá en `memory.md` para qué sirve cada skill o tipo de agente, qué se encontró con él y las preferencias ya confirmadas por el usuario. No repitas preguntas que ya están respondidas ahí.
12. **Cero secretos.** Ni `.env` ni credenciales reales en ejemplos, logs, `memory.md` ni en ningún archivo versionado.

## Documentos relacionados

- `memory.md`: **estado real del proyecto** (qué hay hoy, qué se decidió, qué falta).
- `docs/PLAN.md`: plan de trabajo y estado de cada fase.
- `docs/SECURITY.md`: checklist de seguridad, rotación de secretos y controles implementados.
- `docs/adr/`: decisiones de diseño y su motivo.
