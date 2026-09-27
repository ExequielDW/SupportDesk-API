from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from jose import jwt, JWTError
from services.validators import search_user
from models.user import User
from slowapi import Limiter
from slowapi.util import get_remote_address
from decouple import config

SECRET_KEY = config("SECRET_KEY")
ALGORITHM = config("ALGORITHM")

oauth2 = OAuth2PasswordBearer(tokenUrl="/usuarios/token")


async def authenticator(token: str = Depends(oauth2)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub")
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credencial inválida o token expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial inválida o token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = search_user("username", payload)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial inválida o token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def current_user(user: User = Depends(authenticator)):
    if user.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo o deshabilitado",
        )
    return user


limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
