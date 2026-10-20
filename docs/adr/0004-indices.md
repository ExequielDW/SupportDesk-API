# ADR 0004 — Índices de MongoDB y fin de la unicidad global de títulos

**Estado:** aceptado · **Fecha:** 2026-10-20

## Contexto
La base no tenía **ningún** índice: cada `find_one` era un *collection scan*.
Además, la unicidad del `titulo` de un ticket se validaba a mano
(`search_ticket_response("titulo", ...)`) sobre **toda** la colección, lo que:
1. hacía que un usuario bloqueara un título para todos los demás, y
2. filtraba información entre usuarios (enumeración de títulos ajenos).

## Decisión
Índices creados en el `lifespan` de la app (idempotentes):

| Colección | Índice | Tipo |
| :--- | :--- | :--- |
| `users` | `username` | unique |
| `users` | `email` | unique |
| `tickets` | `(propietario, titulo)` | unique |
| `tickets` | `(propietario, estado)` | compound |
| `tickets` | `(propietario, ultima_actualizacion)` | compound, desc |

La unicidad del título pasa a estar garantizada por el índice
`(propietario, titulo)`: se elimina la query de validación y el 409 sale del
`DuplicateKeyError` (1 round-trip en vez de 2, y sin fuga de información).

## Consecuencias
- `scripts/check_indexes.py` verifica con `explain()` que las queries hot usan `IXSCAN`.
- `scripts/migrate_db.py` debe deduplicar títulos repetidos del mismo propietario
  antes de copiar, o el índice unique fallará al crearse.
