"""Verifica que las queries hot usan índices (IXSCAN) y no collection scans.

Necesita conexión al cluster:    python scripts/check_indexes.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import AsyncMongoClient

from config import DB_NAME, MONGODB_URI

QUERIES = [
    (
        "users por username",
        "users",
        {"username": "ejemplo"},
    ),
    (
        "users por email",
        "users",
        {"email": "ejemplo@example.com"},
    ),
    (
        "tickets por propietario + titulo",
        "tickets",
        {"propietario": "000000000000000000000000", "titulo": "ejemplo"},
    ),
    (
        "tickets por propietario + estado",
        "tickets",
        {"propietario": "000000000000000000000000", "estado": "Abierto"},
    ),
]


async def _explicar_una(coleccion, filtro) -> str:
    plan = await coleccion.find(filtro).explain()
    etapas = plan.get("queryPlanner", {}).get("winningPlan", {})
    return _describir(etapas)


def _describir(etapas: dict) -> str:
    if "inputStage" in etapas:
        return "COLLSCAN (no usa índice)"
    if "stage" in etapas and etapas["stage"] == "IXSCAN":
        indice = etapas.get("indexName", "?")
        return f"IXSCAN (índice: {indice})"
    if "inputStage" in etapas:
        return _describir(etapas["inputStage"])
    if "stage" in etapas:
        return etapas["stage"]
    return "plan desconocido"


async def main_async() -> None:
    cliente = AsyncMongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
    try:
        await cliente.admin.command("ping")
    except Exception as exc:  # noqa: BLE001
        print(f"No se pudo conectar al cluster: {exc}")
        return

    base = cliente.get_database(DB_NAME)
    try:
        print(f"Base: {DB_NAME}")
        print("-" * 70)
        for nombre, coleccion in (("users", base.users), ("tickets", base.tickets)):
            indices = await coleccion.index_information()
            print(f"\nÍndices de {nombre}:")
            for clave, definicion in indices.items():
                unico = " UNIQUE" if definicion.get("unique") else ""
                print(f"  - {clave}: {definicion.get('key')}{unico}")

        print("\n" + "=" * 70)
        print("Plan de ejecución de las queries hot:")
        print("-" * 70)
        for titulo, coleccion, filtro in QUERIES:
            resultado = await _explicar_una(base[coleccion], filtro)
            marca = "OK " if resultado.startswith("IXSCAN") else "!! "
            print(f"{marca}{titulo}: {resultado}")

        # La estadísticas también depende del índice (propietario, estado).
        pipeline = [
            {"$match": {"propietario": "000000000000000000000000"}},
            {"$group": {"_id": "$estado", "cantidad": {"$sum": 1}}},
        ]
        plan = await base.tickets.aggregate(pipeline).explain()
        etapas = plan.get("stages", [{}])[0].get("$cursor", {}).get("queryPlanner", {})
        resultado = _describir(etapas.get("winningPlan", {}))
        marca = "OK " if resultado.startswith("IXSCAN") else "!! "
        print(f"{marca}estadísticas por estado: {resultado}")
    finally:
        await cliente.close()


if __name__ == "__main__":
    asyncio.run(main_async())
