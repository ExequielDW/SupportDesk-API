# ADR 0005 — Modo demo con MongoDB en memoria

**Estado:** aceptado · **Fecha:** 2026-10-20

## Contexto
El proyecto se desarrolla en local y se publica en GitHub; no se despliega en
internet y no se usa Docker. Para que alguien pueda clonar el repositorio y
ver la API funcionando, no puede depender de:

- un cluster de Atlas (además, el cluster anterior dejó de existir),
- Docker para levantar Redis,
- un MongoDB instalado en la máquina.

## Decisión
Mover el fake de MongoDB de `tests/fakes.py` a `database/fake.py` y activarlo
con `MONGODB_FAKE=true` en el `.env`. En ese modo:

- `database/client.py` no crea el `AsyncMongoClient` y entrega el fake como base.
- `ping_db()` no hace nada y los índices se crean sobre el fake.
- Redis es opcional: si `REDIS_URL` está vacío, el cache y los contadores del
  rate limit viven en memoria (y el refresh token se pierde al reiniciar).

## Alternativas consideradas
- **Exigir Atlas o Mongo local**: deja el proyecto sin poder ejecutar sin
  cuentas y sin instalaciones.
- **Docker Compose con Mongo y Redis**: agrega dos servicios y un requisito
  que el proyecto no quiere.
- **SQLite**: obligaría a reescribir la capa de datos.

## Consecuencias
- `pytest` y `uvicorn main:app` funcionan sin ninguna dependencia externa.
- El modo demo **no es un MongoDB**: no hay persistencia, ni transacciones,
  ni replication. Sirve para probar y demostrar, no para datos reales.
- Los tests usan el mismo fake que el modo demo (una sola implementación).
