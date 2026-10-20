"""Validaciones de negocio y acceso a datos.

Todas las funciones que tocan Mongo son `async` y reciben la base como
parámetro: así el código es testeable con fakes y nunca bloquea el event loop.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from models.user import RolEnum, UserCreate
from services.schemas import schema_ticket_propietario, schema_user, schema_user_hash
from services.security import hash_password

# Proyección que nunca trae el hash de la contraseña.
_SIN_PASSWORD = {"password_hash": 0, "password": 0}


def normalizar_username(username: str) -> str:
    return username.strip().lower()


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------- usuarios
async def buscar_usuario(
    db: AsyncDatabase, filtro: dict, *, con_password: bool = False
) -> dict | None:
    """Busca un usuario. Sin `con_password` nunca trae el hash."""
    proyeccion = None if con_password else _SIN_PASSWORD
    documento = await db.users.find_one(filtro, projection=proyeccion)
    if documento is None:
        return None
    if con_password:
        return schema_user_hash(documento)
    return schema_user(documento)


async def buscar_usuario_por_id(
    db: AsyncDatabase, user_id: str, *, con_password: bool = False
) -> dict | None:
    return await buscar_usuario(
        db, {"_id": _a_object_id(user_id)}, con_password=con_password
    )


async def buscar_usuario_por_username(
    db: AsyncDatabase, username: str, *, con_password: bool = False
) -> dict | None:
    return await buscar_usuario(
        db, {"username": normalizar_username(username)}, con_password=con_password
    )


async def buscar_usuario_por_username_o_email(
    db: AsyncDatabase, username: str, email: str
) -> dict | None:
    """Busca por username o por email (para el login)."""
    return await buscar_usuario(
        db,
        {
            "$or": [
                {"username": normalizar_username(username)},
                {"email": normalizar_email(email)},
            ]
        },
        con_password=True,
    )


async def crear_usuario(db: AsyncDatabase, datos: UserCreate) -> dict:
    """Crea un usuario. El rol y `disabled` los decide el servidor."""
    documento = {
        "username": normalizar_username(datos.username),
        "email": normalizar_email(datos.email),
        "password_hash": await hash_password(datos.password),
        "rol": RolEnum.USUARIO.value,
        "disabled": False,
        "fecha_creacion": _ahora(),
    }
    try:
        await db.users.insert_one(documento)
    except DuplicateKeyError as exc:
        # El mensaje es el mismo para username y email: no se puede enumerar
        # qué cuentas existen.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario o el correo ya se encuentran registrados",
        ) from exc
    return schema_user(documento)


# -------------------------------------------------------------------- tickets
async def crear_ticket(
    db: AsyncDatabase, datos, propietario_id: str
) -> dict:
    """Crea un ticket. El título es único **por propietario** (índice unique)."""
    ahora = _ahora()
    documento = {
        "titulo": datos.titulo.strip(),
        "descripcion": datos.descripcion.strip(),
        "categoria": datos.categoria.value,
        "prioridad": datos.prioridad.value,
        "estado": "Abierto",
        "propietario": propietario_id,
        "fecha_creacion": ahora,
        "ultima_actualizacion": ahora,
    }
    try:
        await db.tickets.insert_one(documento)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un ticket tuyo con ese título",
        ) from exc
    return schema_ticket_propietario(documento)


def _a_object_id(valor: str):
    """Convierte a ObjectId si el valor es válido; si no, deja el string."""
    from bson import ObjectId

    if isinstance(valor, ObjectId):
        return valor
    if ObjectId.is_valid(valor):
        return ObjectId(valor)
    return valor
