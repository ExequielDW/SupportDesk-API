from fastapi import APIRouter, status, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from models.user import UserPW, User
from services.validators import (
    validator_user,
    schema_user,
    search_user_pw,
    hash_of_password,
)
from database.client import DB_CLIENT
from decouple import config
from datetime import datetime, timezone, timedelta
from jose import jwt
from routers.auth import current_user, limiter

# credenciales
SECRET_KEY = config("SECRET_KEY")
ACCESS_TOKEN_EXPIRE_MINUTES = int(config("ACCESS_TOKEN_EXPIRE_MINUTES"))
ALGORITHM = config("ALGORITHM")

router = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Usuario o lista de usuarios no encontrados",
            "content": {
                "application/json": {"example": {"detail": "Usuario no encontrado"}}
            },
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Error interno del servidor"
        },
    },
)


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def registro(request: Request, user: UserPW):
    usuario = validator_user(user)
    id_user_insert = DB_CLIENT.users.insert_one(usuario).inserted_id
    new_user = schema_user(DB_CLIENT.users.find_one({"_id": id_user_insert}))
    return User(**new_user)


@router.post("/login", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def loginme(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    usuario_db = search_user_pw("username", form.username)
    if usuario_db is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not hash_of_password.verify(form.password, usuario_db.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contraseña incorrecta",
            headers={"WWW-Authenticate": "Bearer"},
        )
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token_de_acceso = {"sub": usuario_db.username, "exp": expire}
    return {
        "access_token": jwt.encode(token_de_acceso, SECRET_KEY, algorithm=ALGORITHM),
        "token_type": "Bearer",
    }


@router.get("/me", response_model=User, status_code=status.HTTP_200_OK)
async def userme(user: User = Depends(current_user)):
    return user
