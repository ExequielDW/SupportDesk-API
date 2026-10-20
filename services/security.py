"""Hashing de contraseñas y emisión/validación de tokens.

- El hashing usa Argon2id con parámetros ajustados (19 MB / 2 iteraciones).
  Los hashes generados con los parámetros anteriores (64 MB / 3 iteraciones)
  **siguen validando** porque argon2 guarda los parámetros dentro del hash.
- El hashing se ejecuta en un threadpool: son ~10 ms de CPU que no pueden
  bloquear el event loop.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from starlette.concurrency import run_in_threadpool

from config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    SECRET_KEY,
)
from models.user import RolEnum

# Parámetros de Argon2id (recomendación OWASP: m=19 MiB, t=2, p=1).
ARGON2 = Argon2Hasher(time_cost=2, memory_cost=19456, parallelism=1)
PASSWORD_HASHER = PasswordHash((ARGON2,))

# Hash señuelo: se usa cuando el usuario no existe para que el tiempo de
# respuesta sea el mismo que con una contraseña incorrecta (anti-enumeración).
DUMMY_HASH = PASSWORD_HASHER.hash("contrasena-senuelo-para-igualar-tiempos")

TIPO_ACCESS = "access"
TIPO_REFRESH = "refresh"


def _credenciales_401(detalle: str = "Credencial inválida o token expirado"):
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detalle,
        headers={"WWW-Authenticate": "Bearer"},
    )


# --------------------------------------------------------------------- passwords
async def hash_password(password: str) -> str:
    """Hashea una contraseña fuera del event loop."""
    return await run_in_threadpool(PASSWORD_HASHER.hash, password)


async def verify_password(password: str, hash_password_: str) -> bool:
    """Verifica una contraseña fuera del event loop.

    Devuelve False (no lanza) si el hash no es reconocible.
    """
    try:
        return await run_in_threadpool(
            PASSWORD_HASHER.verify, password, hash_password_
        )
    except Exception:  # noqa: BLE001 - hash inválido o de otro algoritmo
        return False


def necesita_rehash(hash_password_: str) -> bool:
    """True si el hash usa parámetros viejos y conviene regenerarlo."""
    try:
        return PASSWORD_HASHER.check_needs_rehash(hash_password_)
    except Exception:  # noqa: BLE001
        return True


# ------------------------------------------------------------------------- JWT
def crear_token(
    *,
    subject: str,
    rol: RolEnum,
    tipo: str,
    minutos: int | None = None,
    dias: int | None = None,
    jti: str | None = None,
    familia: str | None = None,
) -> tuple[str, str, str]:
    """Crea un token. Devuelve (token, jti, familia)."""
    ahora = datetime.now(timezone.utc)
    if dias is not None:
        expira = ahora + timedelta(days=dias)
    else:
        expira = ahora + timedelta(minutes=minutos or ACCESS_TOKEN_EXPIRE_MINUTES)

    identificador = jti or str(uuid.uuid4())
    grupo = familia or str(uuid.uuid4())

    payload = {
        "sub": subject,
        "rol": rol.value if isinstance(rol, RolEnum) else rol,
        "typ": tipo,
        "jti": identificador,
        "fam": grupo,
        "iat": int(ahora.timestamp()),
        "exp": int(expira.timestamp()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, identificador, grupo


def decodificar_token(token: str, tipo_esperado: str) -> dict:
    """Valida firma, expiración, issuer, audience y tipo de token.

    Lanza 401 si algo no cuadra.
    """
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )
    except JWTError:
        raise _credenciales_401() from None

    if payload.get("typ") != tipo_esperado:
        raise _credenciales_401("Tipo de token inválido")
    if not payload.get("sub"):
        raise _credenciales_401()
    return payload
