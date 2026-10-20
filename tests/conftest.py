"""Fixtures de la suite.

Los tests corren contra un fake de MongoDB en memoria: no necesitan Atlas
ni Redis. El cache y el rate limiter se reinician entre tests.
"""

import os

import pytest
from fastapi.testclient import TestClient

# El TestClient usa el host "testserver": hay que permitirlo antes de que
# se importe la app (el middleware se arma en el import).
os.environ.setdefault("ALLOWED_HOSTS", "testserver,localhost,127.0.0.1")

import database.client as db_client
from main import app
from routers.auth import limiter
from services.cache import cache
from tests.fakes import BaseDeDatosFalsa


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    """Reemplaza Mongo por el fake y limpia el estado compartido."""
    base = BaseDeDatosFalsa()
    monkeypatch.setattr(db_client, "DB_CLIENT", base)

    async def _ping() -> None:
        return None

    monkeypatch.setattr("main.ping_db", _ping)

    # El cache en memoria y los contadores del limiter son globales.
    cache._memoria.clear()
    limiter._storage.reset()

    yield base

    cache._memoria.clear()
    limiter._storage.reset()


@pytest.fixture()
def client():
    with TestClient(app) as cliente:
        yield cliente


def _registrar(client, username="usuario", email=None, password="Python2026"):
    return client.post(
        "/usuarios/register",
        json={
            "username": username,
            "email": email or f"{username}@test.com",
            "password": password,
        },
    )


def _login(client, username="usuario", password="Python2026"):
    return client.post(
        "/usuarios/login", data={"username": username, "password": password}
    )


def _token(client, username="usuario", password="Python2026") -> str:
    respuesta = _login(client, username, password)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["access_token"]


@pytest.fixture()
def helpers():
    class Helpers:
        registrar = staticmethod(_registrar)
        login = staticmethod(_login)
        token = staticmethod(_token)

    return Helpers()


@pytest.fixture()
def usuario_autenticado(client, helpers):
    """Registra un usuario y devuelve su access token."""
    helpers.registrar(client, "dueno")
    return helpers.token(client, "dueno")


@pytest.fixture()
def admin(client, helpers, entorno):
    """Registra un usuario y lo convierte en admin (directamente en la base)."""
    helpers.registrar(client, "root")
    entorno.users.documentos[0]["rol"] = "admin"
    return helpers.token(client, "root")
