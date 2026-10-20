"""Fake de MongoDB en memoria para los tests.

Implementa la parte de la API que usa la aplicación (insert, find, update,
aggregate, índices únicos) para que la suite corra **sin** Atlas y sin Redis.

No pretende ser un MongoDB completo: cubre lo que la app necesita.
"""

import copy
from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError


def _coincide(documento: dict, filtro: dict) -> bool:
    """Evalúa un filtro simple (igualdad, $or, $and, $in, $ne)."""
    for clave, valor in filtro.items():
        if clave == "$or":
            if not any(_coincide(documento, sub) for sub in valor):
                return False
        elif clave == "$and":
            if not all(_coincide(documento, sub) for sub in valor):
                return False
        elif clave == "$ne":
            if documento.get(clave) == valor:
                return False
        elif isinstance(valor, dict) and "$in" in valor:
            if documento.get(clave) not in valor["$in"]:
                return False
        elif documento.get(clave) != valor:
            return False
    return True


class CursorFalso:
    def __init__(self, documentos: list[dict]) -> None:
        self._documentos = list(documentos)

    def sort(self, campo: str, direccion: int = 1) -> "CursorFalso":
        self._documentos.sort(
            key=lambda doc: (doc.get(campo) is None, doc.get(campo)),
            reverse=direccion < 0,
        )
        return self

    def skip(self, cantidad: int) -> "CursorFalso":
        self._documentos = self._documentos[cantidad:]
        return self

    def limit(self, cantidad: int) -> "CursorFalso":
        self._documentos = self._documentos[:cantidad]
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        return copy.deepcopy(self._documentos)

    def __aiter__(self):
        return self._iterar()

    async def _iterar(self):
        for documento in self._documentos:
            yield copy.deepcopy(documento)


class ColeccionFalsa:
    def __init__(self, nombre: str) -> None:
        self.nombre = nombre
        self.documentos: list[dict] = []
        self.indices: list[tuple[list[tuple[str, int]], bool, str]] = []

    # ------------------------------------------------------------------ índices
    async def create_indexes(self, indices) -> None:
        for indice in indices:
            especificacion = indice.document
            claves = list(especificacion["key"].items())
            unico = bool(especificacion.get("unique", False))
            nombre = especificacion.get("name", "")
            self.indices.append((claves, unico, nombre))

    def _chequear_unicidad(self, documento: dict) -> None:
        for claves, unico, nombre in self.indices:
            if not unico:
                continue
            valores = tuple(documento.get(campo) for campo, _ in claves)
            for otro in self.documentos:
                if tuple(otro.get(campo) for campo, _ in claves) == valores:
                    raise DuplicateKeyError(
                        f"E11000 duplicate key error collection: {self.nombre} "
                        f"index: {nombre} dup key: {valores}"
                    )

    # ------------------------------------------------------------------ lectura
    def _coincidentes(self, filtro: dict | None) -> list[dict]:
        if not filtro:
            return list(self.documentos)
        return [doc for doc in self.documentos if _coincide(doc, filtro)]

    async def find_one(self, filtro=None, projection=None) -> dict | None:
        encontrados = self._coincidentes(filtro)
        if not encontrados:
            return None
        return copy.deepcopy(encontrados[0])

    def find(self, filtro=None) -> CursorFalso:
        return CursorFalso(self._coincidentes(filtro))

    async def count_documents(self, filtro=None) -> int:
        return len(self._coincidentes(filtro))

    def aggregate(self, pipeline: list[dict]) -> CursorFalso:
        documentos = list(self.documentos)
        for etapa in pipeline:
            if "$match" in etapa:
                documentos = [doc for doc in documentos if _coincide(doc, etapa["$match"])]
            elif "$group" in etapa:
                agrupado: dict = {}
                campo = etapa["$group"]["_id"]
                if isinstance(campo, str) and campo.startswith("$"):
                    campo = campo[1:]
                for doc in documentos:
                    clave = doc.get(campo)
                    agrupado[clave] = agrupado.get(clave, 0) + 1
                documentos = [
                    {"_id": clave, "cantidad": cantidad}
                    for clave, cantidad in agrupado.items()
                ]
        return CursorFalso(documentos)

    # ------------------------------------------------------------------ escritura
    async def insert_one(self, documento: dict):
        # Como hace PyMongo: agrega el _id al documento original.
        documento.setdefault("_id", ObjectId())
        nuevo = copy.deepcopy(documento)
        nuevo.setdefault("fecha_creacion", datetime.now(timezone.utc))
        self._chequear_unicidad(nuevo)
        self.documentos.append(nuevo)
        return _ResultadoInsert(nuevo["_id"])

    async def update_one(self, filtro: dict, actualizacion: dict):
        for documento in self.documentos:
            if _coincide(documento, filtro):
                documento.update(copy.deepcopy(actualizacion.get("$set", {})))
                return _ResultadoUpdate(1, 1)
        return _ResultadoUpdate(0, 0)

    async def find_one_and_update(
        self, filtro: dict, actualizacion: dict, return_document=None, **_extra
    ):

        for documento in self.documentos:
            if _coincide(documento, filtro):
                documento.update(copy.deepcopy(actualizacion.get("$set", {})))
                if actualizacion.get("$unset"):
                    for campo in actualizacion["$unset"]:
                        documento.pop(campo, None)
                return copy.deepcopy(documento)
        return None


class _ResultadoInsert:
    def __init__(self, inserted_id) -> None:
        self.inserted_id = inserted_id
        self.acknowledged = True


class _ResultadoUpdate:
    def __init__(self, matched_count: int, modified_count: int) -> None:
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.acknowledged = True


class BaseDeDatosFalsa:
    def __init__(self) -> None:
        self.users = ColeccionFalsa("users")
        self.tickets = ColeccionFalsa("tickets")

    async def command(self, *_args, **_kwargs) -> dict:
        return {"ok": 1}
