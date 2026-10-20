"""Modelos de usuario.

`rol` y `disabled` **nunca** se aceptan desde el cuerpo de la petición:
el servidor es el único que los asigna (ver docs/adr/0002-rbac.md).
"""

from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class RolEnum(str, Enum):
    USUARIO = "usuario"
    SOPORTE = "soporte"
    ADMIN = "admin"


# Jerarquía de roles: cuanto mayor el número, más permisos.
NIVEL_ROL: dict[RolEnum, int] = {
    RolEnum.USUARIO: 0,
    RolEnum.SOPORTE: 1,
    RolEnum.ADMIN: 2,
}


class User(BaseModel):
    """Respuesta pública de un usuario. Nunca incluye el hash de la password."""

    id: str
    username: str
    email: EmailStr
    rol: RolEnum = RolEnum.USUARIO
    disabled: bool = False


class UserCreate(BaseModel):
    """Datos de registro que envía el cliente.

    No incluye `rol` ni `disabled`: un cliente no puede auto-asignarse admin.
    """

    username: str = Field(
        min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_.-]+$"
    )
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)


class UserUpdateRol(BaseModel):
    """Cambio de rol (solo admin)."""

    rol: RolEnum


class UserUpdateEstado(BaseModel):
    """Habilitación/deshabilitación (solo admin)."""

    disabled: bool
