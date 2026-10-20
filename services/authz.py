"""Autenticación y autorización (RBAC).

- `current_user` valida el access token, revisa la revocación y carga el
  usuario (con cache en Redis para no ir a Mongo en cada request).
- `require_soporte` / `require_admin` aplican la jerarquía de roles.
"""

import json

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pymongo.asynchronous.database import AsyncDatabase

from config import CACHE_USUARIO_TTL
from database.client import get_db
from models.user import NIVEL_ROL, RolEnum, User
from services.cache import cache
from services.security import TIPO_ACCESS, decodificar_token
from services.validators import buscar_usuario_por_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/usuarios/login")


def _401(detalle: str = "Credencial inválida o token expirado"):
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _403(detalle: str = "No tenés permisos para realizar esta acción"):
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detalle)


# ------------------------------------------------------------------ cache de usuario
async def usuario_desde_cache(db: AsyncDatabase, user_id: str) -> dict | None:
    """Devuelve el usuario, usando el cache cuando es posible."""
    clave = f"usuario:{user_id}"
    en_cache = await cache.get(clave)
    if en_cache:
        try:
            return json.loads(en_cache)
        except json.JSONDecodeError:
            await cache.delete(clave)

    usuario = await buscar_usuario_por_id(db, user_id)
    if usuario is not None:
        await cache.set(clave, json.dumps(usuario), CACHE_USUARIO_TTL)
    return usuario


async def invalidar_cache_usuario(user_id: str) -> None:
    """Se llama cuando cambia el rol, el password o el estado de un usuario."""
    await cache.delete(f"usuario:{user_id}")


# ------------------------------------------------------------------ dependencias
async def current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncDatabase = Depends(get_db),
) -> User:
    payload = decodificar_token(token, TIPO_ACCESS)

    jti = payload.get("jti")
    if jti and await cache.exists(f"revocado:{jti}"):
        raise _401("La sesión fue cerrada")

    usuario = await usuario_desde_cache(db, payload["sub"])
    if usuario is None:
        raise _401()
    if usuario.get("disabled"):
        raise _403("Usuario inactivo o deshabilitado")
    return User(**usuario)


def require_rol(minimo: RolEnum):
    """Dependencia que exige un rol mínimo."""

    async def _dependencia(user: User = Depends(current_user)) -> User:
        if NIVEL_ROL[user.rol] < NIVEL_ROL[minimo]:
            raise _403()
        return user

    return _dependencia


require_soporte = require_rol(RolEnum.SOPORTE)
require_admin = require_rol(RolEnum.ADMIN)


def es_staff(user: User) -> bool:
    """True si el usuario es soporte o admin."""
    return NIVEL_ROL[user.rol] >= NIVEL_ROL[RolEnum.SOPORTE]


def puede_ver_ticket(user: User, propietario_id: str) -> bool:
    """El dueño puede ver sus tickets; soporte y admin pueden ver todos."""
    return es_staff(user) or user.id == propietario_id
