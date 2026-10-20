"""Benchmark de latencia de los endpoints hot.

Por defecto corre **en proceso** contra un Mongo falso (no necesita Atlas ni
Redis), así da números reproducibles. Con ``--url`` mide contra un servidor
real.

    python scripts/bench.py --concurrency 50 --requests 500
"""

import argparse
import asyncio
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# El host que usa el cliente en proceso debe estar permitido por el
# TrustedHostMiddleware (igual que en los tests).
os.environ.setdefault("ALLOWED_HOSTS", "testserver,localhost,127.0.0.1")

import httpx

USUARIO = "bench"
PASSWORD = "Python2026"
TICKET = {
    "titulo": "Ticket de benchmark",
    "descripcion": "Generado por el script de benchmark",
    "categoria": "Soporte",
}


def _percentil(valores: list[float], percentil: float) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    indice = min(int(len(ordenados) * percentil / 100), len(ordenados) - 1)
    return ordenados[indice]


async def _preparar(url: str, usar_fake: bool) -> tuple[httpx.AsyncClient, str]:
    if usar_fake:
        import database.client as db_client
        from main import app
        from routers.auth import limiter
        from tests.fakes import BaseDeDatosFalsa

        # El rate limit no forma parte de la medición de la app.
        limiter.enabled = False
        db_client.DB_CLIENT = BaseDeDatosFalsa()
        transporte = httpx.ASGITransport(app=app)
        cliente = httpx.AsyncClient(transport=transporte, base_url="http://testserver")
    else:
        cliente = httpx.AsyncClient(base_url=url, timeout=30.0)

    await cliente.post(
        "/usuarios/register",
        json={
            "username": USUARIO,
            "email": f"{USUARIO}@example.com",
            "password": PASSWORD,
        },
    )
    login = await cliente.post(
        "/usuarios/login", data={"username": USUARIO, "password": PASSWORD}
    )
    if login.status_code != 200:
        raise SystemExit(f"No se pudo iniciar sesión: {login.status_code} {login.text}")
    token = login.json()["access_token"]
    cliente.headers.update({"Authorization": f"Bearer {token}"})
    return cliente, token


async def _medir(cliente: httpx.AsyncClient, path: str, concurrencia: int, requests: int):
    latencias: list[float] = []
    errores = 0
    por_worker = requests // concurrencia
    semaforo = asyncio.Semaphore(concurrencia)

    async def _uno():
        nonlocal errores
        async with semaforo:
            inicio = time.perf_counter()
            try:
                respuesta = await cliente.get(path)
                if respuesta.status_code >= 400:
                    errores += 1
            except Exception:  # noqa: BLE001
                errores += 1
            latencias.append((time.perf_counter() - inicio) * 1000)

    inicio_total = time.perf_counter()
    await asyncio.gather(*[_uno() for _ in range(por_worker * concurrencia)])
    total = time.perf_counter() - inicio_total
    return latencias, errores, total


async def main_async(args) -> None:
    usar_fake = args.url is None
    cliente, _ = await _preparar(args.url or "", usar_fake)
    try:
        # Un ticket para que el listado no devuelva vacío.
        await cliente.post("/tickets/created", json=TICKET)

        print(f"Endpoint: {args.path}")
        print(f"Concurrencia: {args.concurrency} | Requests: {args.requests}")
        print("-" * 58)

        latencias, errores, total = await _medir(
            cliente, args.path, args.concurrency, args.requests
        )
        rps = len(latencias) / total if total else 0.0
        print(f"p50: {_percentil(latencias, 50):8.2f} ms")
        print(f"p95: {_percentil(latencias, 95):8.2f} ms")
        print(f"p99: {_percentil(latencias, 99):8.2f} ms")
        print(f"min: {min(latencias):8.2f} ms")
        print(f"max: {max(latencias):8.2f} ms")
        print(f"media:{statistics.mean(latencias):7.2f} ms")
        print(f"RPS:  {rps:8.1f}")
        print(f"errores: {errores}")
    finally:
        await cliente.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark de la API")
    parser.add_argument("--path", default="/tickets/me", help="endpoint a medir")
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument(
        "--url", default=None, help="URL de un servidor real (por defecto, en proceso)"
    )
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
