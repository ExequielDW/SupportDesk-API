"""Formateadores de documentos de Mongo a diccionarios de Python.

Son la barrera que evita que campos sensibles (hash de la contraseña) se
filtren a las respuestas.
"""


def schema_user(user) -> dict:
    """Proyección pública de un usuario (sin hash de contraseña)."""
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
        "rol": user.get("rol", "usuario"),
        "disabled": bool(user.get("disabled", False)),
    }


def schema_user_hash(user) -> dict:
    """Documento de usuario **con** hash de contraseña (uso interno)."""
    hash_ = user.get("password_hash") or user.get("password") or ""
    return {**schema_user(user), "password_hash": hash_}


def schema_ticket_propietario(ticket) -> dict:
    """Proyección de un ticket."""
    return {
        "id": str(ticket["_id"]),
        "titulo": ticket["titulo"],
        "descripcion": ticket["descripcion"],
        "categoria": ticket["categoria"],
        "prioridad": ticket["prioridad"],
        "estado": ticket.get("estado", "Abierto"),
        "fecha_creacion": ticket["fecha_creacion"],
        "ultima_actualizacion": ticket["ultima_actualizacion"],
        "propietario": ticket["propietario"],
    }
