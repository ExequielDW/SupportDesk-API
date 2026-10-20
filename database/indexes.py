"""Índices de MongoDB.

Se crean en el arranque (idempotente). Son la base para que las queries hot
no hagan *collection scans*: ver docs/adr/0004-indices.md.
"""

from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.asynchronous.database import AsyncDatabase

# Los tickets guardan el propietario como string (el id del usuario).
# Por eso los índices compuestos usan "propietario" y no "_id".
INDICES_USERS = [
    IndexModel([("username", ASCENDING)], unique=True, name="uniq_username"),
    IndexModel([("email", ASCENDING)], unique=True, name="uniq_email"),
]

INDICES_TICKETS = [
    # Unicidad del título **por usuario** (antes era global: un usuario
    # bloqueaba el título a todos los demás y además filtraba información).
    IndexModel(
        [("propietario", ASCENDING), ("titulo", ASCENDING)],
        unique=True,
        name="uniq_titulo_por_propietario",
    ),
    # Alimenta el listado filtrado por estado y las estadísticas.
    IndexModel(
        [("propietario", ASCENDING), ("estado", ASCENDING)],
        name="prop_estado",
    ),
    # Listado ordenado por última actualización.
    IndexModel(
        [("propietario", ASCENDING), ("ultima_actualizacion", DESCENDING)],
        name="prop_ultima_actualizacion",
    ),
]


async def crear_indices(db: AsyncDatabase) -> None:
    """Crea los índices de users y tickets (idempotente)."""
    await db.users.create_indexes(INDICES_USERS)
    await db.tickets.create_indexes(INDICES_TICKETS)
