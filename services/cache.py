"""Cache compartido (Redis) con fallback en memoria.

Se usa para: allowlist de refresh tokens, revocación, cache de usuario,
cache de estadísticas y contadores del rate limit por usuario.

Si Redis no está disponible la app sigue funcionando con un cache en
memoria: eso solo es válido para **un solo proceso** (ver docs/SECURITY.md).
"""

import logging
import time

from config import REDIS_URL

logger = logging.getLogger("supportdesk.cache")


class Cache:
    def __init__(self) -> None:
        self._redis = None
        self._memoria: dict[str, tuple[str, float]] = {}
        self.usando_redis = False

    # ------------------------------------------------------------------ ciclo de vida
    async def connect(self) -> None:
        """Intenta conectarse a Redis. Si no puede, sigue con memoria."""
        if not REDIS_URL:
            logger.warning(
                "REDIS_URL no configurado: se usa cache en memoria "
                "(solo apto para un proceso)"
            )
            return
        try:
            import redis.asyncio as aioredis

            cliente = aioredis.from_url(REDIS_URL, decode_responses=True)
            await cliente.ping()
            self._redis = cliente
            self.usando_redis = True
            logger.info("Cache conectado a Redis")
        except Exception as exc:  # noqa: BLE001 - si falla Redis, no se cae la app
            logger.warning(
                "Redis no disponible (%s): se usa cache en memoria", exc
            )
            self._redis = None

    async def close(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo cerrar Redis: %s", exc)
            self._redis = None

    # ------------------------------------------------------------------ operaciones
    async def get(self, key: str) -> str | None:
        if self._redis is not None:
            return await self._redis.get(key)
        registro = self._memoria.get(key)
        if registro is None:
            return None
        valor, expira = registro
        if expira and expira < time.time():
            self._memoria.pop(key, None)
            return None
        return valor

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        if self._redis is not None:
            if ttl:
                await self._redis.set(key, value, ex=ttl)
            else:
                await self._redis.set(key, value)
            return
        expira = time.time() + ttl if ttl else 0
        self._memoria[key] = (value, expira)

    async def delete(self, key: str) -> None:
        if self._redis is not None:
            await self._redis.delete(key)
            return
        self._memoria.pop(key, None)

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    async def incr(self, key: str, ttl: int) -> int:
        """Incrementa un contador y devuelve el valor nuevo.

        El TTL se aplica solo al crear la clave, de modo que la ventana
        corre desde el primer intento fallido.
        """
        if self._redis is not None:
            valor = await self._redis.incr(key)
            if valor == 1:
                await self._redis.expire(key, ttl)
            return int(valor)

        ahora = time.time()
        registro = self._memoria.get(key)
        if registro is None or (registro[1] and registro[1] < ahora):
            self._memoria[key] = ("1", ahora + ttl)
            return 1
        valor = int(registro[0]) + 1
        self._memoria[key] = (str(valor), registro[1])
        return valor

    async def delete_patron(self, patron: str) -> int:
        """Borra todas las claves que empiezan con `patron` (usado en el
        procedimiento de revocación masiva)."""
        if self._redis is not None:
            claves = [k async for k in self._redis.scan_iter(match=f"{patron}*")]
            if claves:
                await self._redis.delete(*claves)
            return len(claves)
        prefijos = [k for k in self._memoria if k.startswith(patron)]
        for clave in prefijos:
            self._memoria.pop(clave, None)
        return len(prefijos)

    async def vaciar(self) -> None:
        """Limpia todo el cache (usado por los tests y por la revocación masiva)."""
        if self._redis is not None:
            await self._redis.flushdb()
            return
        self._memoria.clear()


cache = Cache()
