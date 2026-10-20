"""Endpoints de usuarios: registro, login, refresh, logout y perfil.

Reglas de seguridad aplicadas acá:
- El login no revela si el usuario existe (mismo mensaje, mismo tiempo).
- El refresh token viaja en cookie httpOnly y se puede revocar.
- `rol` y `disabled` solo los cambia un admin.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    COOKIE_NAME,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    LOGIN_MAX_HORARIO_POR_USUARIO,
    LOGIN_MAX_POR_USUARIO,
    LOGIN_VENTANA_SEGUNDOS,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from database.client import get_db
from models.user import RolEnum, User, UserCreate, UserUpdateEstado, UserUpdateRol
from routers.auth import limiter
from services import ratelimit
from services.audit import registrar_error, registrar_evento
from services.authz import current_user, invalidar_cache_usuario, require_admin
from services.cache import cache
from services.security import (
    DUMMY_HASH,
    TIPO_ACCESS,
    TIPO_REFRESH,
    crear_token,
    decodificar_token,
    hash_password,
    necesita_rehash,
    verify_password,
)
from services.validators import (
    buscar_usuario_por_id,
    buscar_usuario_por_username_o_email,
    crear_usuario,
)

router = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Usuario no encontrado",
            "content": {
                "application/json": {"example": {"detail": "Usuario no encontrado"}}
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Error interno"},
    },
)

_TTL_REFRESH = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
_TTL_ACCESS = ACCESS_TOKEN_EXPIRE_MINUTES * 60


def _ip(request: Request) -> str:
    return request.client.host if request.client else "-"


def _invalidar_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/usuarios")


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def registro(request: Request, datos: UserCreate, db=Depends(get_db)):
    usuario = await crear_usuario(db, datos)
    registrar_evento("registro", usuario=usuario["username"], ip=_ip(request))
    return User(**usuario)


@router.post("/login", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def loginme(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db=Depends(get_db),
):
    """Login. Devuelve el access token y deja el refresh en una cookie httpOnly."""
    ip = _ip(request)
    identidad = form.username.strip().lower()

    usuario = await buscar_usuario_por_username_o_email(db, form.username, form.username)
    hash_ = usuario["password_hash"] if usuario else DUMMY_HASH

    # Se verifica siempre (con un hash señuelo si el usuario no existe) para
    # que el tiempo de respuesta no revele si la cuenta existe.
    credencial_valida = await verify_password(form.password, hash_)

    if usuario is None or not credencial_valida:
        registrar_error("login", usuario=identidad, ip=ip)
        # Límite por usuario: frena el bruteforce distribuido (el de SlowAPI
        # es por IP y no alcanza). Solo cuentan los intentos fallidos, así
        # que un login correcto nunca bloquea a nadie.
        if await ratelimit.excedio(
            f"login:minuto:{identidad}", LOGIN_MAX_POR_USUARIO, LOGIN_VENTANA_SEGUNDOS
        ) or await ratelimit.excedio(
            f"login:hora:{identidad}", LOGIN_MAX_HORARIO_POR_USUARIO, 3600
        ):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiados intentos fallidos. Probá de nuevo más tarde.",
                headers={"Retry-After": str(LOGIN_VENTANA_SEGUNDOS)},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if usuario["disabled"]:
        registrar_error("login", usuario=identidad, ip=ip, detalle="usuario deshabilitado")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Rehashing gradual: si el hash usa los parámetros viejos, se actualiza.
    if necesita_rehash(usuario["password_hash"]):
        nuevo_hash = await hash_password(form.password)
        await db.users.update_one(
            {"_id": _object_id(usuario["id"])}, {"$set": {"password_hash": nuevo_hash}}
        )
        usuario["password_hash"] = nuevo_hash

    await ratelimit.limpiar(f"login:minuto:{identidad}")
    await ratelimit.limpiar(f"login:hora:{identidad}")

    access_token, _, _ = crear_token(
        subject=usuario["id"],
        rol=usuario["rol"],
        tipo=TIPO_ACCESS,
        minutos=ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    refresh_token, jti_refresh, familia = crear_token(
        subject=usuario["id"],
        rol=usuario["rol"],
        tipo=TIPO_REFRESH,
        dias=REFRESH_TOKEN_EXPIRE_DAYS,
    )

    await cache.set(f"refresh:{jti_refresh}", familia, _TTL_REFRESH)
    response.set_cookie(
        key=COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=_TTL_REFRESH,
        path="/usuarios",
    )
    registrar_evento("login", usuario=identidad, ip=ip)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": _TTL_ACCESS,
    }


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refrescar(request: Request, response: Response, db=Depends(get_db)):
    """Rota el refresh token y devuelve un access token nuevo."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decodificar_token(token, TIPO_REFRESH)
    jti = payload.get("jti")
    familia = payload.get("fam")

    # Familia revocada (por ejemplo, tras detectar un reuso).
    if await cache.exists(f"refresh:revocada:{familia}"):
        registrar_error("refresh", usuario=payload.get("sub"), detalle="familia revocada")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reuso de un token ya rotado: se revoca la familia completa.
    if await cache.exists(f"refresh:usado:{jti}"):
        await cache.set(f"refresh:revocada:{familia}", "1", _TTL_REFRESH)
        registrar_error(
            "refresh", usuario=payload.get("sub"), detalle="reuso de refresh token"
        )
        _invalidar_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Allowlist: sin la entrada en cache el token no es válido.
    if not await cache.exists(f"refresh:{jti}"):
        registrar_error("refresh", usuario=payload.get("sub"), detalle="token desconocido")
        _invalidar_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada",
            headers={"WWW-Authenticate": "Bearer"},
        )

    usuario = await buscar_usuario_por_id(db, payload["sub"])
    if usuario is None or usuario["disabled"]:
        await cache.delete(f"refresh:{jti}")
        _invalidar_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Rotación: el jti viejo queda marcado como usado.
    await cache.set(f"refresh:usado:{jti}", "1", _TTL_REFRESH)

    access_token, _, _ = crear_token(
        subject=usuario["id"],
        rol=usuario["rol"],
        tipo=TIPO_ACCESS,
        minutos=ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    refresh_token, jti_nuevo, _ = crear_token(
        subject=usuario["id"],
        rol=usuario["rol"],
        tipo=TIPO_REFRESH,
        dias=REFRESH_TOKEN_EXPIRE_DAYS,
        familia=familia,
    )
    await cache.set(f"refresh:{jti_nuevo}", familia, _TTL_REFRESH)

    response.set_cookie(
        key=COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=_TTL_REFRESH,
        path="/usuarios",
    )
    registrar_evento("refresh", usuario=usuario["username"])
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": _TTL_ACCESS,
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(request: Request, response: Response):
    """Cierra la sesión: revoca el refresh y el access actual."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        try:
            payload = decodificar_token(token, TIPO_REFRESH)
        except HTTPException:
            payload = {}
        jti = payload.get("jti")
        if jti:
            await cache.delete(f"refresh:{jti}")

    encabezado = request.headers.get("authorization", "")
    if encabezado.lower().startswith("bearer "):
        try:
            payload = decodificar_token(encabezado.split()[1], TIPO_ACCESS)
        except HTTPException:
            payload = {}
        jti = payload.get("jti")
        if jti:
            await cache.set(f"revocado:{jti}", "1", _TTL_ACCESS)

    _invalidar_cookie(response)
    registrar_evento("logout")
    return {"mensaje": "Sesión cerrada"}


@router.get("/me", response_model=User, status_code=status.HTTP_200_OK)
async def userme(user: User = Depends(current_user)):
    return user


@router.patch("/{id}/rol", response_model=User, status_code=status.HTTP_200_OK)
async def cambiar_rol(
    id: str, datos: UserUpdateRol, request: Request, db=Depends(get_db),
    user: User = Depends(require_admin),
):
    """Asigna un rol. Solo un admin puede hacerlo."""
    objetivo = await buscar_usuario_por_id(db, id)
    if objetivo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    if objetivo["rol"] == RolEnum.ADMIN and datos.rol != RolEnum.ADMIN:
        admins = await db.users.count_documents(
            {"rol": RolEnum.ADMIN.value, "disabled": False}
        )
        if admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede degradar al último administrador",
            )

    await db.users.update_one(
        {"_id": _object_id(id)}, {"$set": {"rol": datos.rol.value}}
    )
    await invalidar_cache_usuario(id)
    registrar_evento(
        "cambio_rol",
        usuario=user.username,
        ip=_ip(request),
        detalle=f"{id} -> {datos.rol.value}",
    )
    actualizado = await buscar_usuario_por_id(db, id)
    return User(**actualizado)


@router.patch("/{id}/estado", response_model=User, status_code=status.HTTP_200_OK)
async def cambiar_estado(
    id: str, datos: UserUpdateEstado, request: Request, db=Depends(get_db),
    user: User = Depends(require_admin),
):
    """Habilita o deshabilita una cuenta. Solo un admin puede hacerlo."""
    objetivo = await buscar_usuario_por_id(db, id)
    if objetivo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    if datos.disabled and objetivo["rol"] == RolEnum.ADMIN:
        admins = await db.users.count_documents(
            {"rol": RolEnum.ADMIN.value, "disabled": False}
        )
        if admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede deshabilitar al último administrador",
            )

    await db.users.update_one(
        {"_id": _object_id(id)}, {"$set": {"disabled": datos.disabled}}
    )
    await invalidar_cache_usuario(id)
    registrar_evento(
        "cambio_estado_usuario",
        usuario=user.username,
        ip=_ip(request),
        detalle=f"{id} disabled={datos.disabled}",
    )
    actualizado = await buscar_usuario_por_id(db, id)
    return User(**actualizado)


def _object_id(valor: str):
    from bson import ObjectId

    if ObjectId.is_valid(valor):
        return ObjectId(valor)
    return valor
