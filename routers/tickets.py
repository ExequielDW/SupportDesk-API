from fastapi import APIRouter, status, Depends, HTTPException, Request
from models.user import User
from models.ticket import Ticket, TicketResponse
from services.validators import (
    search_ticket_response,
    schema_ticket_propietario,
    buscador_de_tickets,
)
from services.schemas import schema_list
from database.client import DB_CLIENT
from datetime import datetime, timezone
from routers.auth import current_user, limiter
from bson import ObjectId
from pymongo import ReturnDocument
from typing import Optional
from models.ticket import EstadoEnum, PrioridadEnum
from utils.utilidad import estats

# ------------------------------------------------------------------endpoints ----------------------------
router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Ticket o lista de tickets no encontrados",
            "content": {
                "application/json": {"example": {"detail": "Ticket no encontrado"}}
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Error interno del servidor"
        },
    },
)


@router.post(
    "/created", response_model=TicketResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("5/minute")
async def creating_ticket(
    request: Request, ticket: Ticket, user: User = Depends(current_user)
):
    existing_ticket = search_ticket_response("titulo", ticket.titulo)
    if existing_ticket is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El ticket ya se encuentra en nuestra base de datos",
        )
    ticket_dict = ticket.model_dump()
    ticket_dict.pop("id", None)
    ticket_dict["propietario"] = str(user.id)
    ticket_dict["fecha_creacion"] = datetime.now(timezone.utc)
    ticket_dict["ultima_actualizacion"] = datetime.now(timezone.utc)
    ticket_dict_id_insert = DB_CLIENT.tickets.insert_one(ticket_dict).inserted_id
    new_ticket = schema_ticket_propietario(
        DB_CLIENT.tickets.find_one({"_id": ticket_dict_id_insert})
    )
    return TicketResponse(**new_ticket)


@router.get("/me/{id}", status_code=status.HTTP_200_OK, response_model=TicketResponse)
async def get_ticket_by_id(id: str, user: User = Depends(current_user)):
    id_valida = ObjectId.is_valid(id)
    if not id_valida:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id ingresado no es válido",
        )
    existing_ticket = DB_CLIENT.tickets.find_one(
        {"_id": ObjectId(id), "propietario": str(user.id)}
    )
    if not existing_ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado"
        )
    return schema_ticket_propietario(existing_ticket)


@router.put(
    "/update/{id}", status_code=status.HTTP_200_OK, response_model=TicketResponse
)
@limiter.limit("5/minute")
async def update_ticket(
    request: Request, id: str, ticket: Ticket, user: User = Depends(current_user)
):
    id_valida = ObjectId.is_valid(id)
    if not id_valida:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El id ingresado no es válido",
        )
    existing_ticket = DB_CLIENT.tickets.find_one(
        {"_id": ObjectId(id), "propietario": str(user.id)}
    )
    if not existing_ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado"
        )
    ticket_dict = ticket.model_dump()
    ticket_dict.pop("id", None)
    ticket_dict["fecha_creacion"] = existing_ticket["fecha_creacion"]
    ticket_dict["ultima_actualizacion"] = datetime.now(timezone.utc)
    ticket_dict["propietario"] = str(user.id)
    up_ticket = DB_CLIENT.tickets.find_one_and_replace(
        {"_id": ObjectId(id), "propietario": str(user.id)},
        ticket_dict,
        return_document=ReturnDocument.AFTER,
    )
    if not up_ticket:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="El ticket no se actualizo"
        )
    return schema_ticket_propietario(up_ticket)


# filtros
@router.get("/me", status_code=status.HTTP_200_OK, response_model=list[TicketResponse])
@limiter.limit("5/minute")
async def filter_my_tickets(
    request: Request,
    estado: Optional[EstadoEnum] = None,
    prioridad: Optional[PrioridadEnum] = None,
    user: User = Depends(current_user),
):
    tickets = buscador_de_tickets(
        estado=estado, prioridad=prioridad, user_id=str(user.id)
    )
    return tickets or []


@router.get("/stats", status_code=status.HTTP_200_OK)
def estadistica(user: User = Depends(current_user)):
    return estats(str(user.id))
