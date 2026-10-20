"""Migra los datos de la base vieja a la base nueva.

La API se desarrollaba contra una base llamada "suport" (typo). Este script
copia usuarios y tickets a "supportdesk", normalizando los campos que cambió
el modelo (email en minúsculas, `rol`, `disabled`, `password` → `password_hash`)
y conservando los `_id` para no romper las referencias.

    python scripts/migrate_db.py --dry-run    # simula (por defecto)
    python scripts/migrate_db.py --apply      # escribe de verdad
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import AsyncMongoClient

from config import DB_NAME, MONGODB_URI

ORIGEN = os.environ.get("DB_ORIGEN", "suport")


def _normalizar_usuario(documento: dict) -> dict:
    """Adapta un usuario del modelo viejo al nuevo."""
    nuevo = dict(documento)
    nuevo["email"] = str(nuevo.get("email", "")).strip().lower()
    nuevo.setdefault("rol", "usuario")
    nuevo["disabled"] = bool(nuevo.get("disabled", False))
    if "password_hash" not in nuevo and "password" in nuevo:
        nuevo["password_hash"] = nuevo.pop("password")
    nuevo.pop("password", None)
    return nuevo


def _normalizar_ticket(documento: dict) -> dict:
    nuevo = dict(documento)
    nuevo.setdefault("estado", "Abierto")
    nuevo.setdefault("prioridad", "Media")
    return nuevo


async def main_async(aplicar: bool) -> None:
    cliente = AsyncMongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
    try:
        await cliente.admin.command("ping")
    except Exception as exc:  # noqa: BLE001
        print(f"No se pudo conectar al cluster: {exc}")
        return

    origen = cliente.get_database(ORIGEN)
    destino = cliente.get_database(DB_NAME)
    modo = "APLICAR" if aplicar else "SIMULACIÓN"

    print(f"Modo: {modo}")
    print(f"Origen: {ORIGEN} -> Destino: {DB_NAME}")
    print("-" * 60)

    # ------------------------------------------------------------------ usuarios
    usuarios = await origen.users.find({}).to_list(length=None)
    print(f"Usuarios encontrados: {len(usuarios)}")
    preparing = []
    vistos: set[str] = set()
    for documento in usuarios:
        nuevo = _normalizar_usuario(documento)
        clave = (nuevo.get("username"), nuevo.get("email"))
        if clave in vistos:
            print(f"  ! usuario duplicado {clave}, se omite")
            continue
        vistos.add(clave)
        preparing.append(nuevo)

    if aplicar:
        for documento in preparing:
            await destino.users.replace_one(
                {"_id": documento["_id"]}, documento, upsert=True
            )
        print(f"  → {len(preparing)} usuarios escritos")

    # ------------------------------------------------------------------- tickets
    tickets = await origen.tickets.find({}).to_list(length=None)
    print(f"Tickets encontrados: {len(tickets)}")
    normalizados = []
    titulos: set[tuple] = set()
    omitidos = 0
    for documento in tickets:
        nuevo = _normalizar_ticket(documento)
        clave = (nuevo.get("propietario"), nuevo.get("titulo"))
        if clave in titulos:
            # El índice único (propietario, titulo) no permite duplicados.
            omitidos += 1
            continue
        titulos.add(clave)
        normalizados.append(nuevo)
    if omitidos:
        print(f"  ! {omitidos} tickets omitidos por título duplicado (mismo propietario)")

    if aplicar:
        for documento in normalizados:
            await destino.tickets.replace_one(
                {"_id": documento["_id"]}, documento, upsert=True
            )
        print(f"  → {len(normalizados)} tickets escritos")

    print("-" * 60)
    if aplicar:
        print("Migración completa. Recordá crear los índices (se hace al arrancar la API).")
    else:
        print("Simulación terminada. Usá --apply para escribir los cambios.")

    await cliente.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migra datos entre bases")
    parser.add_argument(
        "--apply", action="store_true", help="Escribe los cambios (por defecto simula)"
    )
    args = parser.parse_args()
    asyncio.run(main_async(args.apply))
