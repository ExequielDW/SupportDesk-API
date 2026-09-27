from models.user import User, UserPW
from models.ticket import TicketResponse, Ticket


# --------------------------- esquemas de usuario ---------------------------
def schema_user(user) -> dict:
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
        "disabled": user["disabled"],
    }


def schema_user_pw(user) -> dict:
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "disabled": user["disabled"],
        "email": user["email"],
        "password": user["password"],
    }


# --------------------------- esquemas de ticket ---------------------------


def schema_ticket(ticket) -> dict:
    return {
        "id": str(ticket["_id"]),
        "titulo": ticket["titulo"],
        "descripcion": ticket["descripcion"],
        "categoria": ticket["categoria"],
        "prioridad": ticket["prioridad"],
    }


def schema_ticket_propietario(ticket) -> dict:
    return {
        "id": str(ticket["_id"]),
        "titulo": ticket["titulo"],
        "descripcion": ticket["descripcion"],
        "categoria": ticket["categoria"],
        "prioridad": ticket["prioridad"],
        "estado": ticket["estado"],
        "fecha_creacion": ticket["fecha_creacion"],
        "ultima_actualizacion": ticket["ultima_actualizacion"],
        "propietario": ticket["propietario"],
    }


def schema_list(tickets) -> list:
    return [schema_ticket_propietario(ticket) for ticket in tickets]
