"""Endpoints de tickets.

Acceso: el dueño ve sus tickets; soporte y admin ven todos.
Las mutaciones usan `$set` (nunca `find_one_and_replace`) para no perder campos
y para poder usar índices.
"""

import json
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pymongo import ReturnDocument

from config import CACHE_STATS_TTL
from database.client import get_db
from models.ticket import (
    EstadoEnum,
    PrioridadEnum,
    TicketCreate,
    TicketEstadoUpdate,
    TicketResponse,
    TicketUpdate,
    transicion_valida,
)
from models.user import RolEnum, User
from routers.auth import limiter
from services.audit import registrar_evento
from services.authz import current_user, es_staff, require_soporte
from services.cache import cache
from services.validators import crear_ticket

router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Ticket no encontrado",
            "content": {
                "application/json": {"example": {"detail": "Ticket no encontrado"}}
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Error interno"},
    },
)

_LIMITE_MAXIMO = 100


def _ip(request: Request) -> str:
    return request.client.host if request.client else "-"


def _object_id(valor: str) -> ObjectId | str:
    if ObjectId.is_valid(valor):
        return ObjectId(valor)
    return valor


def _filtro_ticket(id: str, user: User) -> dict:
    """Filtro de un ticket: el dueño solo accede a los suyos."""
    filtro: dict = {"_id": _object_id(id)}
    if not es_staff(user):
        filtro["propietario"] = user.id
    return filtro


@router.post("/created", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def creating_ticket(
    request: Request, ticket: TicketCreate, user: User = Depends(current_user), db=Depends(get_db)
):
    nuevo = await crear_ticket(db, ticket, user.id)
    return TicketResponse(**nuevo)


@router.get("/me/{id}", status_code=status.HTTP_200_OK, response_model=TicketResponse)
async def get_ticket_by_id(id: str, user: User = Depends(current_user), db=Depends(get_db)):
    if not ObjectId.is_valid(id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="El id ingresado no es válido"
        )
    ticket = await db.tickets.find_one(_filtro_ticket(id, user))
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
    return TicketResponse(**_a_respuesta(ticket))


@router.put("/update/{id}", status_code=status.HTTP_200_OK, response_model=TicketResponse)
@limiter.limit("10/minute")
async def update_ticket(
    request: Request,
    id: str,
    ticket: TicketUpdate,
    user: User = Depends(current_user),
    db=Depends(get_db),
):
    """Actualiza un ticket. El estado NO se toca acá (tiene su propio endpoint)."""
    if not ObjectId.is_valid(id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="El id ingresado no es válido"
        )

    ahora = datetime.now(timezone.utc)
    actualizacion = await db.tickets.find_one_and_update(
        _filtro_ticket(id, user),
        {
            "$set": {
                "titulo": ticket.titulo.strip(),
                "descripcion": ticket.descripcion.strip(),
                "categoria": ticket.categoria.value,
                "prioridad": ticket.prioridad.value,
                "ultima_actualizacion": ahora,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not actualizacion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
    return TicketResponse(**_a_respuesta(actualizacion))


@router.get("/me", status_code=status.HTTP_200_OK, response_model=list[TicketResponse])
@limiter.limit("30/minute")
async def filter_my_tickets(
    request: Request,
    estado: EstadoEnum | None = None,
    prioridad: PrioridadEnum | None = None,
    limite: int = Query(default=50, ge=1, le=_LIMITE_MAXIMO),
    saltar: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db=Depends(get_db),
):
    """Lista paginada de los tickets del usuario autenticado."""
    consulta: dict = {"propietario": user.id}
    if estado is not None:
        consulta["estado"] = estado.value
    if prioridad is not None:
        consulta["prioridad"] = prioridad.value

    documentos = await (
        db.tickets.find(consulta)
        .sort("ultima_actualizacion", -1)
        .skip(saltar)
        .limit(limite)
        .to_list(length=limite)
    )
    return [TicketResponse(**_a_respuesta(doc)) for doc in documentos]


@router.get("/stats", status_code=status.HTTP_200_OK)
async def estadistica(user: User = Depends(current_user), db=Depends(get_db)):
    """Estadísticas de los tickets del usuario (cacheadas por 30 s)."""
    clave = f"stats:{user.id}"
    en_cache = await cache.get(clave)
    if en_cache:
        return json.loads(en_cache)

    estadisticas = await _calcular_estadisticas(db, {"propietario": user.id})
    await cache.set(clave, _a_json(estadisticas), CACHE_STATS_TTL)
    return estadisticas


@router.get("", status_code=status.HTTP_200_OK, response_model=list[TicketResponse])
@limiter.limit("30/minute")
async def listar_tickets(
    request: Request,
    estado: EstadoEnum | None = None,
    prioridad: PrioridadEnum | None = None,
    propietario: str | None = None,
    limite: int = Query(default=50, ge=1, le=_LIMITE_MAXIMO),
    saltar: int = Query(default=0, ge=0),
    user: User = Depends(require_soporte),
    db=Depends(get_db),
):
    """Listado global de tickets. Solo para soporte y administradores."""
    consulta: dict = {}
    if estado is not None:
        consulta["estado"] = estado.value
    if prioridad is not None:
        consulta["prioridad"] = prioridad.value
    if propietario:
        consulta["propietario"] = propietario

    documentos = await (
        db.tickets.find(consulta)
        .sort("ultima_actualizacion", -1)
        .skip(saltar)
        .limit(limite)
        .to_list(length=limite)
    )
    return [TicketResponse(**_a_respuesta(doc)) for doc in documentos]


@router.get("/stats/global", status_code=status.HTTP_200_OK)
async def estadisticas_globales(
    propietario: str | None = None,
    user: User = Depends(require_soporte),
    db=Depends(get_db),
):
    """Estadísticas de todos los tickets. Solo para soporte y administradores."""
    consulta = {"propietario": propietario} if propietario else {}
    return await _calcular_estadisticas(db, consulta)


@router.patch("/{id}/estado", status_code=status.HTTP_200_OK, response_model=TicketResponse)
async def cambiar_estado(
    id: str,
    datos: TicketEstadoUpdate,
    request: Request,
    user: User = Depends(current_user),
    db=Depends(get_db),
):
    """Cambia el estado del ticket validando las transiciones permitidas."""
    if not ObjectId.is_valid(id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="El id ingresado no es válido"
        )

    filtro = _filtro_ticket(id, user)
    ticket = await db.tickets.find_one(filtro)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")

    actual = EstadoEnum(ticket.get("estado", EstadoEnum.ABIERTO.value))
    es_admin = user.rol == RolEnum.ADMIN

    if not transicion_valida(actual, datos.estado, es_admin):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No se puede pasar de '{actual.value}' a '{datos.estado.value}'",
        )

    ahora = datetime.now(timezone.utc)
    actualizado = await db.tickets.find_one_and_update(
        filtro,
        {"$set": {"estado": datos.estado.value, "ultima_actualizacion": ahora}},
        return_document=ReturnDocument.AFTER,
    )
    if not actualizado:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")

    registrar_evento(
        "cambio_estado_ticket",
        usuario=user.username,
        ip=_ip(request),
        detalle=f"{id}: {actual.value} -> {datos.estado.value}",
    )
    await cache.delete(f"stats:{ticket['propietario']}")
    return TicketResponse(**_a_respuesta(actualizado))


# ------------------------------------------------------------------- auxiliares
async def _calcular_estadisticas(db, consulta: dict) -> dict:
    """Agrega los tickets por estado (usa el índice propietario+estado)."""
    pipeline = [
        {"$match": consulta},
        {"$group": {"_id": "$estado", "cantidad": {"$sum": 1}}},
    ]
    estadisticas = {
        "total": 0,
        "abiertos": 0,
        "en_progreso": 0,
        "resueltos": 0,
        "cerrados": 0,
    }
    mapa_estados = {
        EstadoEnum.ABIERTO.value: "abiertos",
        EstadoEnum.EN_PROCESO.value: "en_progreso",
        EstadoEnum.RESUELTO.value: "resueltos",
        EstadoEnum.CERRADO.value: "cerrados",
    }
    async for item in db.tickets.aggregate(pipeline):
        estado = item["_id"]
        cantidad = item["cantidad"]
        estadisticas["total"] += cantidad
        clave = mapa_estados.get(estado)
        if clave:
            estadisticas[clave] += cantidad
    return estadisticas


def _a_respuesta(ticket) -> dict:
    return {
        "id": str(ticket["_id"]),
        "titulo": ticket["titulo"],
        "descripcion": ticket["descripcion"],
        "categoria": ticket["categoria"],
        "prioridad": ticket["prioridad"],
        "estado": ticket.get("estado", EstadoEnum.ABIERTO.value),
        "fecha_creacion": ticket["fecha_creacion"],
        "ultima_actualizacion": ticket["ultima_actualizacion"],
        "propietario": ticket["propietario"],
    }


def _a_json(datos: dict) -> str:
    return json.dumps(datos)
