"""Rate limiting por usuario (complementa el límite por IP de SlowAPI).

El límite por IP frena el abuso desde una IP; el límite por usuario frena el
bruteforce distribuido (muchas IPs contra la misma cuenta).
"""

from fastapi import HTTPException, status

from services.cache import cache


async def excedio(llave: str, limite: int, ventana: int) -> bool:
    """Suma un intento al contador y devuelve True si se pasó el límite."""
    total = await cache.incr(llave, ventana)
    return total > limite


async def enforce(
    llave: str,
    limite: int,
    ventana: int,
    mensaje: str = "Demasiados intentos. Probá de nuevo más tarde.",
) -> None:
    """Lanza 429 si el contador superó el límite."""
    if await excedio(llave, limite, ventana):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=mensaje,
            headers={"Retry-After": str(ventana)},
        )


async def limpiar(llave: str) -> None:
    """Resetea el contador (login exitoso)."""
    await cache.delete(llave)
