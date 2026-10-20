"""Cliente de MongoDB (asíncrono).

El acceso a datos es siempre `await` y pasa por `get_db()`, que es una
dependencia de FastAPI: en los tests se reemplaza con un fake en memoria
usando `app.dependency_overrides[get_db]`.
"""

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from config import (
    DB_NAME,
    MONGODB_URI,
    POOL_MAX_SIZE,
    POOL_MIN_SIZE,
)

_client = AsyncMongoClient(
    MONGODB_URI,
    maxPoolSize=POOL_MAX_SIZE,
    minPoolSize=POOL_MIN_SIZE,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=10000,
    retryWrites=True,
    tz_aware=True,
)

DB_CLIENT: AsyncDatabase = _client.get_database(DB_NAME)


def get_db() -> AsyncDatabase:
    """Dependencia de FastAPI que entrega la base de datos."""
    return DB_CLIENT


async def ping_db() -> None:
    """Verifica que el cluster responde. Se usa en el lifespan."""
    await _client.admin.command("ping")


async def close_db() -> None:
    """Cierra el pool de conexiones. Se usa en el lifespan."""
    await _client.close()
