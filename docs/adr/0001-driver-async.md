# ADR 0001 — Driver asíncrono de MongoDB

**Estado:** aceptado · **Fecha:** 2026-10-20

## Contexto
Todos los handlers son `async def`, pero el acceso a datos usaba `pymongo` síncrono.
Cada query a Atlas (50-200 ms de red) **congelaba el event loop** del proceso,
serializando las requests concurrentes. El hashing de contraseñas hacía lo mismo
(44 ms de CPU por login dentro del loop).

## Decisión
Migrar a `AsyncMongoClient` de `pymongo>=4.13` (nativa, sin dependencias extra) y
usar `Depends(get_db())` para inyectar la base. El hashing pasa a ejecutarse en un
threadpool con `run_in_threadpool`.

## Alternativas consideradas
- **Motor**: async más maduro, pero en mantenimiento y con una dependencia más.
- **Handlers `def` (threadpool de FastAPI)**: cambio mínimo, pero el control de la
  concurrencia queda en manos de Starlette y no se puede usar `await` en el código
  de negocio.
- **Dejarlo síncrono**: descartado, era el problema.

## Consecuencias
- Todo el código de `services/` y `routers/` pasa a ser `async`.
- Los tests pueden inyectar un fake con `app.dependency_overrides[get_db]`.
- `pymongo` deja de necesitar `motor`.
