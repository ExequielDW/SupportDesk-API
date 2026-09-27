from models.user import User, UserPW
from models.ticket import Ticket, TicketResponse
from fastapi import HTTPException, status
from database.client import DB_CLIENT
from services.schemas import (
    schema_user,
    schema_user_pw,
    schema_ticket_propietario,
    schema_list,
)
from pwdlib import PasswordHash
from models.ticket import EstadoEnum, PrioridadEnum
from typing import Optional

hash_of_password = PasswordHash.recommended()


# ---------------------------------------  Validaciones de usuario ------------------------------
def search_user(field: str, key):
    found = DB_CLIENT.users.find_one({field: key})
    if found is None:
        return None
    return User(**schema_user(found))


def search_user_pw(field: str, key):
    found = DB_CLIENT.users.find_one({field: key})
    if found is None:
        return None
    return UserPW(**schema_user_pw(found))


def validator_name(user: User):
    if not user.username or not user.username.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El campo nombre debe estar completado",
        )
    if search_user("username", user.username) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nombre ya se encuentra en la base de datos",
        )


def validator_mail(user: User):
    email_clean = user.email.strip().lower()
    if search_user("email", email_clean) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo electronico ya se encuentra registrado",
        )


def validator_user(user: UserPW):
    validator_name(user)
    validator_mail(user)
    user_dict = user.model_dump()
    user_dict["password"] = hash_of_password.hash(user_dict["password"])
    user_dict.pop("id", None)
    return user_dict


# ------------------------- Validaciones de tickets ----------------------------------


def search_ticket_response(field: str, key):
    found = DB_CLIENT.tickets.find_one({field: key})
    if found is None:
        return None
    return TicketResponse(**schema_ticket_propietario(found))


def buscador_de_tickets(
    user_id: str,
    estado: Optional[EstadoEnum] = None,
    prioridad: Optional[PrioridadEnum] = None,
):
    query = {"propietario": str(user_id)}

    # Solo agregamos al filtro los valores que realmente se enviaron
    if estado is not None:
        query["estado"] = estado.value
    if prioridad is not None:
        query["prioridad"] = prioridad.value

    tickets_find = DB_CLIENT.tickets.find(query)
    return schema_list(tickets_find)
