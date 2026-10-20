# 🎫 SupportDesk API

API REST de gestión de tickets de soporte técnico. **FastAPI + MongoDB (driver async) + SlowAPI + JWT**, con control de roles, sesiones revocables y tests que corren sin base de datos.

---

## ⚡ Características

* **Autenticación con sesiones revocables:** access token 15 min + refresh token rotativo de 7 días en cookie `httpOnly`, con revocación real (allowlist en Redis) y detección de reuso.
* **Autorización RBAC:** roles `usuario` < `soporte` < `admin`, con dependencias de FastAPI y protección anti-escalación.
* **Gestión de tickets (CRUD):** creación, lectura, listado paginado y filtrable, actualización y cambio de estado con transiciones validadas.
* **Rate limiting en dos planos:** por IP (SlowAPI + Redis) y por usuario (Redis), más auditoría de eventos de seguridad.
* **Rendimiento:** driver asíncrono real, índices en Mongo, cache de usuarios y estadísticas, paginación y respuestas `orjson`.
* **Validación estricta:** Pydantic v2 con límites de longitud, roles controlados por el servidor y límite de tamaño del body.

---

## 🛠️ Tecnologías

| Componente | Tecnología |
| :--- | :--- |
| **Lenguaje** | Python 3.10+ |
| **Framework Web** | FastAPI |
| **Base de Datos** | MongoDB (PyMongo async) |
| **Cache / sesiones** | Redis (con fallback en memoria en desarrollo) |
| **Rate Limiter** | SlowAPI |
| **Seguridad** | Argon2id (pwdlib), python-jose (JWT) |
| **Configuración** | python-decouple |
| **JSON** | orjson |

---

## 📁 Estructura

```text
SupportDesk API/
├── config.py              # configuración central (lee .env)
├── main.py                # app FastAPI, lifespan, middlewares
├── database/
│   ├── client.py          # AsyncMongoClient + get_db()
│   └── indexes.py         # índices (unique por usuario/email, por propietario)
├── models/                # Pydantic v2 (user con roles, ticket con transiciones)
├── routers/               # endpoints (auth, users, tickets)
├── services/              # security (hash+JWT), authz (RBAC), cache, ratelimit, audit, validators, schemas
├── utils/                 # middlewares, agregaciones
├── scripts/               # bench, check_indexes, migrate_db
├── tests/                 # fakes en memoria + suite
└── docs/                  # PLAN.md, SECURITY.md, adr/
```

---

## 🚀 Puesta en marcha

```bash
# 1. Dependencias
pip install -r requirements.txt

# 2. Variables de entorno
cp .env.example .env      # en Windows: copy .env.example .env
# completá URI, SECRET_KEY y (opcional) REDIS_URL

# 3. Redis (opcional en desarrollo, hay fallback en memoria)
docker compose up -d redis

# 4. Correr
uvicorn main:app --reload --port 8000
```

Documentación interactiva: <http://localhost:8000/docs> (deshabilitada con `ENVIRONMENT=production`).

---

## 🧪 Tests y benchmarks

```bash
pytest -q                                  # no necesita Mongo ni Redis
python scripts/bench.py --concurrency 50 --requests 500
python scripts/check_indexes.py            # verifica IXSCAN (necesita Atlas)
```

---

## 🔐 Seguridad

* `docs/SECURITY.md`: checklist de producción, rotación de secretos y controles implementados.
* `docs/adr/`: decisiones y su motivo (driver async, RBAC, refresh tokens, índices).
* `docs/PLAN.md`: plan de trabajo y estado de cada fase.

**Nunca** commitear `.env`. La versión sin secretos es `.env.example`.

---

## 📡 Endpoints principales

| Método | Ruta | Acceso | Descripción |
| :--- | :--- | :--- | :--- |
| POST | `/usuarios/register` | público | Alta de usuario (el rol lo asigna el servidor) |
| POST | `/usuarios/login` | público | Devuelve access token + cookie de refresh |
| POST | `/usuarios/refresh` | cookie | Rota el refresh token |
| POST | `/usuarios/logout` | opcional | Revoca la sesión |
| GET | `/usuarios/me` | autenticado | Perfil del usuario |
| PATCH | `/usuarios/{id}/rol` | admin | Asigna un rol |
| PATCH | `/usuarios/{id}/estado` | admin | Habilita/deshabilita una cuenta |
| POST | `/tickets/created` | autenticado | Crea un ticket |
| GET | `/tickets/me` | autenticado | Mis tickets (paginado y filtrable) |
| GET | `/tickets/me/{id}` | dueño o staff | Detalle de un ticket |
| PUT | `/tickets/update/{id}` | dueño o staff | Actualiza un ticket |
| PATCH | `/tickets/{id}/estado` | dueño o staff | Cambia el estado (transiciones validadas) |
| GET | `/tickets` | soporte/admin | Listado global |
| GET | `/tickets/stats` | autenticado | Estadísticas propias |
| GET | `/tickets/stats/global` | soporte/admin | Estadísticas globales |
